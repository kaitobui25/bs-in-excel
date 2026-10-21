"""HTTP endpoint contract tests using a fake browser (no Chrome required)."""
import http.client
import json
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import HTTPServer

from text_browser.service import AddinHandler, BASE_URL, PORT
from text_browser.filter_settings import FilterSettingsStore
from text_browser.service import WEB_ROOT


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
        cls.temp = tempfile.TemporaryDirectory()
        cls.handler = type("TestAddinHandler", (AddinHandler,), {
            "service": FakeService(),
            "filter_settings": FilterSettingsStore(
                WEB_ROOT / "sensitive-words.json", Path(cls.temp.name) / "sensitive-words.json")
        })
        cls.server = HTTPServer(("127.0.0.1", 0), cls.handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

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

    def test_sensitive_filter_assets_and_rendering_integration(self):
        _, html, _ = self.make_request("GET", "/")
        html = html.decode("utf-8")
        self.assertIn('src="/sensitive-filter.js"', html)
        self.assertLess(html.index('src="/sensitive-filter.js"'), html.index('src="/app.js"'))
        for path, mime in [("/sensitive-filter.js", "application/javascript"),
                           ("/filter-settings.js", "application/javascript"),
                           ("/sensitive-words.json", "application/json")]:
            code, data, content_type = self.make_request("GET", path)
            self.assertEqual(code, 200)
            self.assertIn(mime, content_type)
            self.assertGreater(len(data), 50)
        _, config, _ = self.make_request("GET", "/sensitive-words.json")
        self.assertIn("pokemon", json.loads(config)["keywords"])
        self.assertIn("nintendo", json.loads(config)["keywords"])
        self.assertIn("pokecenter", json.loads(config)["keywords"])
        self.assertIn("Poké Center", json.loads(config)["keywords"])
        self.assertIn("center", json.loads(config)["compoundSuffixes"])
        _, script, _ = self.make_request("GET", "/app.js")
        script = script.decode("utf-8")
        self.assertIn('await filterReady', script)
        self.assertIn('entry.node.nodeValue = sensitiveFilter.maskText(entry.display)', script)
        self.assertIn('entry.display = prefix + translated.join("") + suffix', script)
        self.assertIn('captureHistoryNodes()', script)
        self.assertIn('refreshVisibleFilter()', script)
        self.assertIn('maskedPageAddress = sensitiveFilter.maskUrl(url)', script)
        self.assertIn('displayAddress(page.url)', script)
        self.assertIn('elements.address.value === maskedPageAddress', script)
        self.assertIn('link.href = url', script)

    def test_filter_settings_menu_assets(self):
        _, html, _ = self.make_request("GET", "/")
        _, script, _ = self.make_request("GET", "/app.js")
        html, script = html.decode("utf-8"), script.decode("utf-8")
        for element in ("settings-toggle", "settings-menu", "settings-filter",
                        "filter-panel", "filter-keywords", "filter-save", "filter-cancel"):
            self.assertIn(f'id="{element}"', html)
        self.assertLess(html.index('src="/filter-settings.js"'), html.index('src="/app.js"'))
        self.assertIn('fetch("/api/filter-settings"', script)
        self.assertIn('entry.display = prefix + translated.join("") + suffix', script)
        self.assertIn('return applyFilterSettings(result.settings)', script)

    def test_filter_settings_get_post_and_validation(self):
        code, body, _ = self.make_request("GET", "/api/filter-settings")
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["ok"])
        data = json.dumps({"keywords": ["zoo", "Pokémon", "Alpha", "  alpha  "]}).encode()
        code, body, _ = self.make_request("POST", "/api/filter-settings", body=data)
        self.assertEqual(code, 200)
        result = json.loads(body)["settings"]
        self.assertEqual(result["keywords"], ["Alpha", "Pokémon", "zoo"])
        self.assertIn("compoundSuffixes", result)
        code, body, _ = self.make_request("GET", "/api/filter-settings")
        self.assertEqual(json.loads(body)["settings"]["keywords"], result["keywords"])
        for body in ({"keywords": "not-list"}, {"keywords": ["a\nb"]},
                     {"keywords": ["a"], "enabled": False}, {"mask": {}}):
            code, _, _ = self.make_request("POST", "/api/filter-settings",
                                           body=json.dumps(body).encode())
            self.assertEqual(code, 400)
        code, _, _ = self.make_request("POST", "/api/filter-settings", body=b"{bad json")
        self.assertEqual(code, 400)
        code, _, _ = self.make_request("POST", "/api/filter-settings",
                                       body=b'{"keywords":[1]}')
        self.assertEqual(code, 400)
        code, body, _ = self.make_request("GET", "/api/filter-settings")
        self.assertEqual(json.loads(body)["settings"]["keywords"], result["keywords"])

    def test_filter_settings_write_requires_same_origin(self):
        code, _, _ = self.make_request("POST", "/api/filter-settings",
                                       body=b'{"keywords":[]}', origin="https://other.example")
        self.assertEqual(code, 403)
        code, _, _ = self.make_request("GET", "/api/filter-settings",
                                       origin="https://other.example")
        self.assertEqual(code, 403)

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
