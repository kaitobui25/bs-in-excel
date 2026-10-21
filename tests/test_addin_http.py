"""HTTP endpoint contract tests using a fake browser (no Chrome required)."""
import http.client
import json
import threading
import unittest
from unittest.mock import patch
from http.server import HTTPServer

from text_browser.service import AddinHandler, BASE_URL, PORT


class FakeService:
    connected = False

    def open(self, action, value):
        if action == "search":
            return {"ok": True, "page": {"title": "Google", "url": "https://www.google.com",
                    "text": "Result", "links": []}}
        if action == "history":
            return {"ok": True, "history": [], "page": None}
        return {"ok": False, "error": "Bad action"}


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.handler = type("TestAddinHandler", (AddinHandler,), {"service": FakeService()})
        cls.server = HTTPServer(("127.0.0.1", 0), cls.handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def make_request(self, method, path, body=None, origin=BASE_URL):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        headers = {"Host": "localhost:" + str(PORT), "Origin": origin}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        result = connection.getresponse()
        data = result.read()
        content_type = result.getheader("Content-Type")
        code = result.status
        connection.close()
        return code, data, content_type

    def test_health(self):
        code, data, _ = self.make_request("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(data)["ok"])

    def test_html_and_js_available(self):
        for path, mime in [("/", "text/html"), ("/app.js", "application/javascript"), ("/style.css", "text/css")]:
            code, data, header = self.make_request("GET", path)
            self.assertEqual(code, 200)
            self.assertIn(mime, header)
            self.assertGreater(len(data), 100)

    def test_reader_has_no_visible_status_bar_or_duplicate_url(self):
        code, data, _ = self.make_request("GET", "/")
        self.assertEqual(code, 200)
        html = data.decode("utf-8")
        self.assertIn('id="status" class="sr-only"', html)
        self.assertNotIn('class="statusbar"', html)
        self.assertNotIn('id="page-url"', html)
        self.assertIn('id="address"', html)

    def test_facebook_post_preview_assets(self):
        _, script, _ = self.make_request("GET", "/app.js")
        _, css, _ = self.make_request("GET", "/style.css")
        script, css = script.decode("utf-8"), css.decode("utf-8")
        self.assertIn('make("button", expanded ? "See less" : "See more"', script)
        self.assertIn('window.addEventListener("resize", updatePostPreviews)', script)
        self.assertIn('expandedPosts.clear()', script)
        self.assertIn('fetch("/api/jobs"', script)
        self.assertIn('-webkit-line-clamp: 4', css)
        self.assertIn('.block-post.post-collapsed .post-links', css)

    def test_reader_menu_and_translation_controls(self):
        _, html, _ = self.make_request("GET", "/")
        _, script, _ = self.make_request("GET", "/app.js")
        html, script = html.decode("utf-8"), script.decode("utf-8")
        for element in ("scroll-top", "translate-en", "translate-vi", "translate-original"):
            self.assertIn(f'id="{element}"', html)
        self.assertIn('fetch("/api/translate"', script)

    @patch("text_browser.service.translate_segments", return_value=["Hello", "Good morning"])
    def test_translate_json_route(self, translate):
        body = json.dumps({"target": "en", "texts": ["こんにちは", "Chào buổi sáng"]}).encode()
        code, response, _ = self.make_request("POST", "/api/translate", body)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(response)["texts"], ["Hello", "Good morning"])
        translate.assert_called_once_with(["こんにちは", "Chào buổi sáng"], "en")
        code, _, _ = self.make_request("POST", "/api/translate", body, "https://evil.example")
        self.assertEqual(code, 403)

    def test_search_action_json(self):
        body = json.dumps({"action": "search", "value": "siemens tia portal"}).encode()
        code, data, _ = self.make_request("POST", "/api/browse", body)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)["page"]["title"], "Google")

    def test_invalid_origin_rejected(self):
        body = json.dumps({"action": "search", "value": "test"}).encode()
        code, _, _ = self.make_request("POST", "/api/browse", body, "https://not-local.example")
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
