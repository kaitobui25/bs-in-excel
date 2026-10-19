import tempfile
import unittest
from pathlib import Path

from text_browser.__main__ import TextBrowserApp
from text_browser.browser import Link, PageData
from text_browser.history import HistoryStore


class FakeBrowser:
    def __init__(self):
        self.calls = []

    def navigate(self, url):
        self.calls.append(("navigate", url))
        return PageData("Page", url, "Content", [Link("Next", "https://test.invalid/next")])

    def search(self, query):
        self.calls.append(("search", query))
        return PageData("Google", "https://www.google.com/search?q=test", "Search results", [])


class FakeExcel:
    def __init__(self):
        self.statuses = []
        self.history_items = []
        self.help_count = 0

    def show_page(self, page):
        return page.links

    def show_history(self, items):
        self.history_items = list(items)

    def show_help(self):
        self.help_count += 1

    def status(self, value):
        self.statuses.append(value)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.browser = FakeBrowser()
        self.excel = FakeExcel()
        self.app = TextBrowserApp(
            self.excel, self.browser, HistoryStore(Path(self.tmp.name) / "history.json")
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_siemens_navigation(self):
        url = "https://www.siemens.com/ja-jp/products/tia-portal/"
        self.app.execute(url)
        self.assertEqual(self.browser.calls[-1], ("navigate", url))
        self.assertEqual(self.app.history.entries[0].url, url)

    def test_search_and_open_link(self):
        self.app.execute("siemens tia portal")
        self.assertEqual(self.browser.calls[-1], ("search", "siemens tia portal"))
        self.app.execute("https://example.com")
        self.app.execute(":open 1")
        self.assertEqual(self.browser.calls[-1], ("navigate", "https://test.invalid/next"))

    def test_history_shows_saved_entries(self):
        self.app.execute("https://example.com")
        self.app.execute(":history")
        self.assertEqual(self.excel.history_items[0].url, "https://example.com")
        self.app.execute(":open 1")
        self.assertEqual(self.browser.calls[-1], ("navigate", "https://example.com"))


if __name__ == "__main__":
    unittest.main()
