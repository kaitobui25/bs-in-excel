import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from text_browser.browser import Link, PageData
from text_browser.history import HistoryStore
from text_browser.service import BrowserService


class DummyBrowser:
    def __init__(self):
        self.commands = []
        self.connect_count = 0

    def connect(self):
        self.connect_count += 1

    def navigate(self, url):
        self.commands.append(("navigate", url))
        return PageData("Test", url, "text only", [Link("Related", "https://example.com/related")])

    def search(self, value):
        self.commands.append(("search", value))
        return PageData("Google", "https://www.google.com/search?q=siemens", "Results", [])

    def back(self):
        return None

    def forward(self):
        return None

    def reload(self):
        return PageData("Reload", "https://example.com", "reloaded", [])

    def close(self):
        pass


class AddinBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.browser = DummyBrowser()
        self.service = BrowserService(
            browser=self.browser,
            history=HistoryStore(Path(self.temp.name) / "history.json"),
        )

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def test_search_from_addin(self):
        response = self.service.open("search", "siemens tia portal")
        self.assertTrue(response["ok"])
        self.assertEqual(self.browser.commands, [("search", "siemens tia portal")])

    def test_visit_siemens(self):
        url = "https://www.siemens.com/ja-jp/products/tia-portal/"
        response = self.service.open("navigate", url)
        self.assertTrue(response["ok"])
        self.assertEqual(response["page"]["url"], url)
        self.assertEqual(self.browser.connect_count, 1)
        self.assertEqual(self.service.open("history")["history"][0]["url"], url)

    def test_reject_dangerous_schemes(self):
        for url in ["file:///C:/secret", "javascript:alert(1)", "https://a:b@example.com"]:
            response = self.service.open("navigate", url)
            self.assertFalse(response["ok"], url)
        self.assertEqual(self.browser.commands, [])

    def test_unsupported_and_empty_search(self):
        self.assertFalse(self.service.open("unknown")["ok"])
        self.assertFalse(self.service.open("search", " ")["ok"])


if __name__ == "__main__":
    unittest.main()
