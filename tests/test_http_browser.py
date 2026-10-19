import unittest
from unittest.mock import patch

from text_browser.http_browser import HttpTextBrowser


class FakeResponse:
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url, html):
        self.url = url
        self.content = html.encode("utf-8")

    def raise_for_status(self):
        pass


class HttpBrowserTests(unittest.TestCase):
    def setUp(self):
        self.browser = HttpTextBrowser()

    def tearDown(self):
        self.browser.close()

    def test_html_and_back_navigation(self):
        def fake_get(url, timeout):
            return FakeResponse(url, "<html><head><title>Siemens</title></head>"
                "<body><main><h1>TIA Portal</h1><p>Engineering software</p>"
                "<a href='/more'>Read more</a><img src='/image.png'></main></body></html>")
        with patch.object(self.browser.session, "get", side_effect=fake_get):
            page = self.browser.navigate("https://www.siemens.com/page")
            self.assertEqual(page.title, "Siemens")
            self.assertIn("TIA Portal", page.text)
            self.assertEqual(page.links[0].url, "https://www.siemens.com/more")
            self.assertIsNone(self.browser.back())
            self.browser.navigate("https://www.siemens.com/next")
            self.assertEqual(self.browser.back().url, "https://www.siemens.com/page")

    def test_google_block_has_honest_fallback(self):
        def fake_get(url, timeout):
            if "google.com" in url:
                return FakeResponse(url, "<html><title>Google Search</title><body>"
                    "Please click here if you are not redirected.</body></html>")
            return FakeResponse(url, "<html><title>Yahoo results</title><main>"
                "<p>TIA Portal software details</p>"
                "<a href='https://www.siemens.com/ja-jp/products/tia-portal/'>Siemens TIA Portal</a>"
                "</main></html>")
        with patch.object(self.browser.session, "get", side_effect=fake_get):
            page = self.browser.search("siemens tia portal")
        self.assertIn("Yahoo!", page.title)
        self.assertIn("KHÔNG phải Google", page.text)
        self.assertEqual(page.links[0].title, "Mở Google trong trình duyệt ngoài")
        self.assertIn("q=siemens+tia+portal", page.links[0].url)


if __name__ == "__main__":
    unittest.main()
