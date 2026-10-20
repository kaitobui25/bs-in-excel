import json
import unittest
from unittest.mock import Mock, patch

from requests import Response
from requests.exceptions import Timeout

from text_browser.browser import NeoTextBrowser
from text_browser.neo_mcp import NeoMcpClient, NeoMcpError, NeoPage, _decode_response


def response(body, *, session=None, status=200):
    result = Response()
    result.status_code = status
    result._content = body.encode("utf-8")
    if session:
        result.headers["mcp-session-id"] = session
    return result


class NeoMcpTests(unittest.TestCase):
    def test_sse_handles_heartbeat_and_utf8(self):
        raw = 'data: heartbeat\n\ndata: {"jsonrpc":"2.0","result":{"title":"Tiếng Việt"}}\n\n'
        self.assertEqual(_decode_response(response(raw))["result"]["title"], "Tiếng Việt")

    def test_initializes_once_and_reads_structured_result(self):
        client = NeoMcpClient()
        init = response('{"jsonrpc":"2.0","result":{}}', session="s1")
        notification = response("")
        run = response(json.dumps({"jsonrpc": "2.0", "result": {
            "structuredContent": {"ok": True, "value": {"pageId": 9}}
        }}))
        with patch.object(client.http, "post", side_effect=[init, notification, run, run]) as post:
            self.assertEqual(client.run("return 9;"), {"pageId": 9})
            self.assertEqual(client.run("return 9;"), {"pageId": 9})
        self.assertEqual(post.call_count, 4)
        self.assertEqual(post.call_args.kwargs["headers"]["mcp-session-id"], "s1")
        client.close()

    def test_run_failure_is_not_silently_retried(self):
        client = NeoMcpClient()
        client.session_id = "old"
        with patch.object(client.http, "post", return_value=response("Not Found: Session not found", status=404)) as post:
            with self.assertRaises(NeoMcpError):
                client.run("return 1;")
        self.assertIsNone(client.session_id)
        post.assert_called_once()
        client.close()

    def test_timeout_keeps_session_for_later_tab_cleanup(self):
        client = NeoMcpClient()
        client.session_id = "s1"
        with patch.object(client.http, "post", side_effect=Timeout("read timeout")):
            with self.assertRaises(NeoMcpError):
                client.run("return true;")
        self.assertEqual(client.session_id, "s1")
        client.close()

    def test_page_reuses_its_own_tab_and_escapes_url(self):
        client = Mock(session_id="s1")
        client.run.side_effect = [12, {"pageId": 12, "data": "one"}, {"pageId": 12, "data": "two"}, True]
        page = NeoPage(client)
        first = page.run("return 'one';", url='https://example.com/?q="test"')
        second = page.run("return 'two';", url="https://example.com/next")
        self.assertEqual((first, second), ("one", "two"))
        self.assertIn("browser.open('about:blank')", client.run.call_args_list[0].args[0])
        self.assertIn('q=\\"test\\"', client.run.call_args_list[1].args[0])
        self.assertIn("browser.page(12)", client.run.call_args_list[2].args[0])
        self.assertIn("tab.ownership === 'mine'", client.run.call_args_list[2].args[0])
        page.close()
        self.assertIn("browser.page(12).close()", client.run.call_args_list[3].args[0])
        self.assertIn("tab?.ownership === 'mine'", client.run.call_args_list[3].args[0])
        client.close.assert_called_once()

    def test_stale_tab_requires_new_tab_before_retry(self):
        client = Mock(session_id="s1")
        client.run.side_effect = [
            12, {"pageId": 12, "data": "first"},
            NeoMcpError("NEO_TAB_UNAVAILABLE"),
            15, {"pageId": 15, "data": "fresh"}, True,
        ]
        page = NeoPage(client)
        self.assertEqual(page.run("return 'first';", url="https://example.com/"), "first")
        self.assertEqual(page.run("return true;", url="https://example.com/second"), "fresh")
        self.assertEqual(page.page_id, 15)
        page.close()

    def test_navigation_recovers_expired_session_once(self):
        client = Mock(session_id="old")
        def perform(script):
            if client.run.call_count == 1:
                client.session_id = None
                raise NeoMcpError("404: Session not found")
            if client.run.call_count == 2:
                client.session_id = "new"
                return 22
            return {"pageId": 22, "data": "reconnected"}
        client.run.side_effect = perform
        page = NeoPage(client)
        page.page_id = 12
        self.assertEqual(page.run("return true;", url="https://facebook.com/"), "reconnected")
        self.assertEqual(client.run.call_count, 3)
        self.assertEqual(page.page_id, 22)

    def test_non_navigation_does_not_retry_expired_session(self):
        client = Mock(session_id="old")
        client.run.side_effect = NeoMcpError("NEO_TAB_UNAVAILABLE")
        page = NeoPage(client)
        page.page_id = 8
        with self.assertRaises(NeoMcpError):
            page.run("return true;")
        self.assertEqual(client.run.call_count, 1)
        self.assertIsNone(page.page_id)

    def test_open_retries_expired_session_without_existing_page(self):
        client = Mock(session_id="old")
        def perform(script):
            if client.run.call_count == 1:
                client.session_id = None
                raise NeoMcpError("Session not found")
            if client.run.call_count == 2:
                client.session_id = "new"
                return 33
            return {"pageId": 33, "data": "ok"}
        client.run.side_effect = perform
        page = NeoPage(client)
        self.assertEqual(page.run("return true;", url="https://facebook.com/"), "ok")
        self.assertEqual(page.page_id, 33)

    def test_full_browser_back_without_history(self):
        with patch("text_browser.browser.NeoPage") as factory:
            page = factory.return_value
            page.page_id = None
            browser = NeoTextBrowser()
            self.assertIsNone(browser.back())
            page.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
