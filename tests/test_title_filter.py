import unittest

from text_browser.title_filter import TITLE_HOSTS, visible_title


class TitleFilterTests(unittest.TestCase):
    def test_siemens_domains_are_allowed(self):
        self.assertEqual(TITLE_HOSTS, ("siemens.com",))
        for url in (
            "https://siemens.com/",
            "https://www.siemens.com/ja-jp/products/tia-portal/",
            "https://support.industry.siemens.com/cs/",
            "https://SIEMENS.COM:443/products",
            "https://www.siemens.com./ja-jp/",
        ):
            with self.subTest(url=url):
                self.assertEqual(visible_title(url, "Siemens TIA Portal"), "Siemens TIA Portal")

    def test_other_sites_are_hidden_even_if_title_says_siemens(self):
        for url in (
            "https://www.facebook.com/",
            "https://m.facebook.com/groups/example/",
            "https://x.com/siemens",
            "https://www.youtube.com/watch?v=abc",
            "https://www.reuters.com/technology/",
            "https://www.nytimes.com/",
            "https://example.com/",
            "https://fake-siemens.com/",
            "https://siemens.com.evil.example/",
            "https://notsiemens.com/",
            "https://evil.example/path/siemens.com",
            "https://evil.example/?next=https://siemens.com",
            "https://siemens.com@evil.example/",
            "file:///siemens.com/page",
        ):
            with self.subTest(url=url):
                self.assertEqual(visible_title(url, "Siemens Official - Great News"), "")

    def test_empty_and_whitespace_titles_are_hidden(self):
        self.assertEqual(visible_title("https://siemens.com/", ""), "")
        self.assertEqual(visible_title("https://siemens.com/", "   "), "")


if __name__ == "__main__":
    unittest.main()
