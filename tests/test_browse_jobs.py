"""Navigation concurrency and progressive snapshots, without a live Neo tab."""

import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from text_browser.browser import PageData
from text_browser.history import HistoryStore
from text_browser.http_browser import HttpTextBrowser
from text_browser.jobs import BrowseJobs
from text_browser.service import BrowserService


def page(url, text):
    return PageData("Test title", url, text, [], blocks=[
        {"kind": "paragraph", "parts": [{"type": "text", "text": text}]}
    ])


class BrowseJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.service = BrowserService(history=HistoryStore(Path(self.temp.name) / "history.json"))
        self.jobs = BrowseJobs(self.service)

    def tearDown(self):
        self.jobs.close()
        self.service.close()
        self.temp.cleanup()

    def wait_for(self, job_id, statuses, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self.jobs.snapshot(job_id)
            if data["status"] in statuses:
                return data
            time.sleep(0.015)
        self.fail(f"Job {job_id} did not reach {statuses}")

    def test_first_snapshot_arrives_before_completed_document(self):
        unblock = threading.Event()
        started = threading.Event()
        url = "https://example.com/article"

        def slow_fetch(_browser, _url, on_progress=None, is_cancelled=None):
            on_progress(page(url, "First meaningful paragraph"))
            started.set()
            self.assertTrue(unblock.wait(3))
            return page(url, "First meaningful paragraph\nSecond paragraph")

        with patch.object(HttpTextBrowser, "_fetch", slow_fetch):
            before = time.monotonic()
            job_id = self.jobs.start("navigate", url)["job_id"]
            self.assertLess(time.monotonic() - before, 0.2)
            self.assertTrue(started.wait(2))
            partial = self.wait_for(job_id, {"partial"})
            self.assertIn("First meaningful", partial["result"]["page"]["text"])
            self.assertEqual(partial["result"]["page"]["title"], "")
            self.assertEqual(self.service.browser.urls, [url])
            self.assertNotIn("Second paragraph", partial["result"]["page"]["text"])
            unblock.set()
            complete = self.wait_for(job_id, {"complete"})
            self.assertIn("Second paragraph", complete["result"]["page"]["text"])
            self.assertGreater(complete["version"], partial["version"])
            self.assertIsNone(self.jobs.snapshot(job_id, complete["version"])["result"])

    def test_new_http_request_supersedes_blocked_http_without_waiting(self):
        unblock = threading.Event()
        started = threading.Event()
        slow_url, fast_url = "https://example.com/slow", "https://example.com/fast"

        def fetch(_browser, url, on_progress=None, is_cancelled=None):
            if url == slow_url:
                started.set()
                self.assertTrue(unblock.wait(3))
            return page(url, "Content " + url)

        with patch.object(HttpTextBrowser, "_fetch", fetch):
            first = self.jobs.start("navigate", slow_url)["job_id"]
            self.assertTrue(started.wait(2))
            second = self.jobs.start("navigate", fast_url)["job_id"]
            result = self.wait_for(second, {"complete"})
            self.assertEqual(result["result"]["page"]["url"], fast_url)
            self.assertEqual(self.jobs.snapshot(first)["status"], "cancelled")
            unblock.set()
            time.sleep(0.05)
            self.assertEqual(self.service.browser.urls, [fast_url])
            self.assertEqual(self.service.current.url, fast_url)
            self.assertEqual([entry.url for entry in self.service.history.entries], [fast_url])

    def test_expired_job_does_not_commit_late_result(self):
        unblock, started = threading.Event(), threading.Event()

        def fetch(_browser, url, on_progress=None, is_cancelled=None):
            started.set()
            self.assertTrue(unblock.wait(3))
            return page(url, "Late result must not appear")

        with patch.object(HttpTextBrowser, "_fetch", fetch), \
             patch("text_browser.jobs.JOB_DEADLINE", 0.01):
            job_id = self.jobs.start("navigate", "https://example.com/timeout")["job_id"]
            self.assertTrue(started.wait(2))
            time.sleep(0.025)
            result = self.jobs.snapshot(job_id)
            self.assertEqual(result["status"], "error")
            self.assertIn("Quá thời gian", result["error"])
            unblock.set()
            time.sleep(0.05)
            self.assertEqual(self.service.browser.urls, [])
            self.assertIsNone(self.service.current)

    def test_neo_feed_does_not_block_regular_http_page(self):
        started, unblock = threading.Event(), threading.Event()
        fb_url, http_url = "https://www.facebook.com/", "https://example.com/independent"

        class FakeFacebook:
            def navigate(self, url, on_progress=None):
                started.set()
                if not unblock.wait(3):
                    raise AssertionError("Neo worker stuck")
                return page(url, "Facebook finished")

            def close(self):
                pass

        self.service.browser._facebook = FakeFacebook()

        def fetch(_browser, url, on_progress=None, is_cancelled=None):
            return page(url, "Regular HTML loaded")

        with patch.object(HttpTextBrowser, "_fetch", fetch):
            old = self.jobs.start("navigate", fb_url)["job_id"]
            self.assertTrue(started.wait(2))
            new = self.jobs.start("navigate", http_url)["job_id"]
            result = self.wait_for(new, {"complete"})
            self.assertEqual(result["result"]["page"]["url"], http_url)
            unblock.set()
            self.assertEqual(self.jobs.snapshot(old)["status"], "cancelled")
            self.assertEqual(self.service.browser.urls, [http_url])

    def test_history_back_forward_reload_and_invalid_actions(self):
        def fetch(_browser, url, on_progress=None, is_cancelled=None):
            return page(url, "Regular HTML loaded")

        with patch.object(HttpTextBrowser, "_fetch", fetch):
            for url in ("https://example.com/one", "https://example.com/two"):
                self.wait_for(self.jobs.start("navigate", url)["job_id"], {"complete"})
            self.assertEqual(self.service.browser.position, 1)
            result = self.wait_for(self.jobs.start("back")["job_id"], {"complete"})
            self.assertEqual(result["result"]["page"]["url"], "https://example.com/one")
            self.assertEqual(self.service.browser.position, 0)
            result = self.wait_for(self.jobs.start("forward")["job_id"], {"complete"})
            self.assertEqual(result["result"]["page"]["url"], "https://example.com/two")
            self.wait_for(self.jobs.start("reload")["job_id"], {"complete"})
            self.assertEqual(len(self.service.browser.urls), 2)
            self.assertEqual(self.service.browser.position, 1)
            history = self.wait_for(self.jobs.start("history")["job_id"], {"complete"})
            self.assertEqual(history["result"]["history"][0]["url"], "https://example.com/two")
            self.assertFalse(self.jobs.start("navigate", "file:///secret")["ok"])
            self.assertFalse(self.jobs.start("search", "")["ok"])
            self.assertIsNone(self.jobs.snapshot("unknown"))
            error = self.wait_for(self.jobs.start("forward")["job_id"], {"error"})
            self.assertIn("Không có trang sau", error["error"])


class HttpStreamingTests(unittest.TestCase):
    def test_streamed_html_produces_preview_before_full_body(self):
        url = "https://example.com/large"
        start = ("<html><head><title>Article</title></head><body><main>" +
                 "<p>" + "This is the first paragraph. " * 1400 + "</p>").encode()
        end = b"<p>Final paragraph appears only in the full response.</p></main></body></html>"

        class StreamingResponse:
            headers = {"Content-Type": "text/html"}

            def __init__(self):
                self.url = url

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size):
                for idx in range(0, len(start), chunk_size):
                    yield start[idx:idx + chunk_size]
                yield end

        browser = HttpTextBrowser()
        previews = []
        try:
            with patch.object(browser.session, "get", return_value=StreamingResponse()):
                complete = browser._fetch(url, on_progress=previews.append)
            self.assertEqual(len(previews), 1)
            self.assertIn("first paragraph", previews[0].text)
            self.assertNotIn("Final paragraph", previews[0].text)
            self.assertIn("Final paragraph", complete.text)
        finally:
            browser.close()


if __name__ == "__main__":
    unittest.main()
