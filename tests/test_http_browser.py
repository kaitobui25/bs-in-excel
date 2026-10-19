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
        self.assertEqual(page.title, "Kết quả tìm kiếm: siemens tia portal")
        self.assertNotIn("dự phòng", page.title)
        self.assertNotIn("KHÔNG phải Google", page.text)
        self.assertEqual(page.links[0].url, "https://www.siemens.com/ja-jp/products/tia-portal/")
        self.assertEqual(page.blocks[1]["parts"][0]["type"], "link")

    def test_image_positions_and_clickable_links_in_order(self):
        html = ("<html><body><main><h2>Products</h2><p>Before "
                "<a href='/detail'>open <strong>the page</strong></a> after "
                "<img src='/photo.jpg'> more</p><p>Next item</p>"
                "<img width='1' height='1' src='/tracking.gif'>"
                "<script>alert(1)</script></main></body></html>")
        with patch.object(self.browser.session, "get",
                          return_value=FakeResponse("https://example.com/path", html)):
            page = self.browser.navigate("https://example.com/path")
        self.assertEqual([block["kind"] for block in page.blocks], ["heading", "paragraph", "paragraph"])
        parts = page.blocks[1]["parts"]
        self.assertEqual([part["type"] for part in parts],
                         ["text", "link", "text", "image", "text"])
        self.assertEqual(parts[1]["text"], "open the page")
        self.assertEqual(parts[1]["url"], "https://example.com/detail")
        self.assertEqual(sum(part["type"] == "image"
                             for block in page.blocks for part in block["parts"]), 1)
        self.assertNotIn("alert", page.text)

    def test_linked_image_keeps_click_destination(self):
        html = ("<html><body><main><a href='/product'><img src='pic.png'></a>"
                "<a href='javascript:alert(1)'>bad link</a></main></body></html>")
        with patch.object(self.browser.session, "get",
                          return_value=FakeResponse("https://example.com/page", html)):
            page = self.browser.navigate("https://example.com/page")
        self.assertEqual(page.blocks[0]["parts"][0]["type"], "image")
        self.assertEqual(page.blocks[0]["parts"][0]["url"], "https://example.com/product")
        self.assertEqual(page.links, [])

    def test_page_fragment_target_and_no_astro_noise(self):
        html = ("<html><body><main><a href='#details'>Details</a>"
                "<section id='details'><h2>More</h2><p>astro:end</p>"
                "<p>Information</p></section></main></body></html>")
        with patch.object(self.browser.session, "get",
                          return_value=FakeResponse("https://example.com/page", html)):
            page = self.browser.navigate("https://example.com/page")
        self.assertEqual(page.links[0].url, "https://example.com/page#details")
        self.assertTrue(any(block.get("id") == "details" for block in page.blocks))
        self.assertNotIn("astro:end", page.text)


if __name__ == "__main__":
    unittest.main()
