"""HTTP endpoint contract tests using a fake browser (no Chrome required)."""
import http.client
import json
import threading
import unittest
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
