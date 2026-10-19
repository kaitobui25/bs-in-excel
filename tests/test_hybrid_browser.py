import unittest
from unittest.mock import Mock, patch

from text_browser.browser import PageData
from text_browser.hybrid_browser import HybridTextBrowser, is_facebook_url


class HybridBrowserTests(unittest.TestCase):
    def test_facebook_hosts_only(self):
        for url in (
            "https://facebook.com/", "https://www.facebook.com/Siemens/",
            "https://m.facebook.com/", "https://l.facebook.com/l.php?u=a",
            "https://fb.watch/test", "https://fb.com/",
        ):
            self.assertTrue(is_facebook_url(url), url)
        for url in (
            "https://notfacebook.com/", "https://facebook.com.example.org/",
            "https://www.siemens.com/", "https://facebook.com.attacker.example/",
        ):
            self.assertFalse(is_facebook_url(url), url)

    def test_facebook_is_lazy_and_reused(self):
        browser = HybridTextBrowser()
        fake = Mock()
        fake.navigate.side_effect = lambda url: PageData("Facebook", url, "public text", [])
        try:
            with patch("text_browser.hybrid_browser.FacebookChrome", return_value=fake) as factory, \
                 patch("text_browser.http_browser.HttpTextBrowser._fetch", autospec=True,
                       side_effect=lambda _self, url: PageData("Other", url, "normal HTML", [])):
                first = browser.navigate("https://www.siemens.com/")
                self.assertEqual(first.title, "Other")
                factory.assert_not_called()
                browser.navigate("https://www.facebook.com/")
                browser.navigate("https://www.facebook.com/Siemens/")
                self.assertEqual(factory.call_count, 1)
                self.assertEqual(browser.back().url, "https://www.facebook.com/")
                self.assertEqual(browser.back().url, "https://www.siemens.com/")
                self.assertEqual(browser.forward().url, "https://www.facebook.com/")
        finally:
            browser.close()
        fake.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
