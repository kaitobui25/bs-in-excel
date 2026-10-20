"""Exercise the async API over a real threaded localhost HTTP server."""

import http.client
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from text_browser.browser import PageData
from text_browser.history import HistoryStore
from text_browser.http_browser import HttpTextBrowser
from text_browser.jobs import BrowseJobs
from text_browser.service import AddinHandler, BASE_URL, PORT, BrowserService


class JobApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.service = BrowserService(history=HistoryStore(Path(self.temp.name) / "history.json"))
        self.jobs = BrowseJobs(self.service)
        handler = type("JobsTestHandler", (AddinHandler,),
                       {"service": self.service, "jobs": self.jobs})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.jobs.close()
        self.service.close()
        self.temp.cleanup()

    def call(self, method, path, body=None, origin=BASE_URL):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Host": f"localhost:{PORT}", "Origin": origin}
        if body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body)
        try:
            conn.request(method, path, body, headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_job_ack_polling_and_health_during_blocked_download(self):
        started = threading.Event()
        unblock = threading.Event()
        url = "https://example.com/slow"

        def slow(_browser, _url, on_progress=None, is_cancelled=None):
            on_progress(PageData("Example", url, "Initial text", []))
            started.set()
            if not unblock.wait(3):
                raise AssertionError("Blocked HTTP worker never released")
            return PageData("Example", url, "Complete text", [])

        with patch.object(HttpTextBrowser, "_fetch", slow):
            start = time.monotonic()
            status, ack = self.call("POST", "/api/jobs", {"action": "navigate", "value": url})
            self.assertEqual(status, 202)
            self.assertLess(time.monotonic() - start, 0.5)
            self.assertEqual(len(ack["job_id"]), 32)
            self.assertTrue(started.wait(2))

            start = time.monotonic()
            code, health = self.call("GET", "/api/health")
            self.assertEqual((code, health["ok"]), (200, True))
            self.assertLess(time.monotonic() - start, 0.5)
            code, update = self.call("GET", f'/api/jobs/{ack["job_id"]}?since=0')
            self.assertEqual(code, 200)
            self.assertEqual(update["status"], "partial")
            self.assertEqual(update["result"]["page"]["text"], "Initial text")
            version = update["version"]
            _, unchanged = self.call("GET", f'/api/jobs/{ack["job_id"]}?since={version}')
            self.assertIsNone(unchanged["result"])

            unblock.set()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                _, update = self.call("GET", f'/api/jobs/{ack["job_id"]}?since={version}')
                if update["status"] == "complete":
                    break
                time.sleep(0.02)
            self.assertEqual(update["status"], "complete")
            self.assertEqual(update["result"]["page"]["text"], "Complete text")

    def test_job_security_and_input_validation(self):
        code, _ = self.call("POST", "/api/jobs", {"action": "navigate", "value": "javascript:alert(1)"})
        self.assertEqual(code, 400)
        code, _ = self.call("POST", "/api/jobs", {"action": "history"}, origin="https://attacker.example")
        self.assertEqual(code, 403)
        code, _ = self.call("GET", "/api/jobs/invalid")
        self.assertEqual(code, 404)
        code, _ = self.call("GET", "/api/jobs/" + "f" * 32, origin="https://attacker.example")
        self.assertEqual(code, 403)
        code, _ = self.call("GET", "/api/jobs/" + "f" * 32 + "?since=abc")
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
