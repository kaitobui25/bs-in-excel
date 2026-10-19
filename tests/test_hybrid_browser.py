import unittest
from unittest.mock import Mock, patch

from text_browser.browser import PageData
from text_browser.hybrid_browser import FacebookChrome, HybridTextBrowser, is_facebook_url


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

    def test_profile_three_attached_without_launching_new_chrome(self):
        page = Mock()
        page.is_closed.return_value = False
        page.url = "https://www.facebook.com/Siemens/"
        page.title.return_value = "Siemens | Facebook"
        page.content.return_value = (
            "<html><body><main><h1>Siemens</h1>"
            "<a href='/about'>About</a></main></body></html>"
        )
        context = Mock()
        context.new_page.return_value = page
        browser = Mock()
        browser.contexts = [context]
        runtime = Mock()
        runtime.chromium.connect_over_cdp.return_value = browser
        manager = Mock()
        manager.start.return_value = runtime

        with patch("text_browser.hybrid_browser.sync_playwright", return_value=manager), \
             patch("text_browser.hybrid_browser.read_cdp_endpoint",
                   return_value="ws://127.0.0.1:53859/devtools/browser/test"):
            client = FacebookChrome()
            result = client.navigate("https://www.facebook.com/Siemens/")
            self.assertEqual(result.title, "Siemens | Facebook")
            self.assertEqual(len(result.links), 1)
            runtime.chromium.connect_over_cdp.assert_called_once()
            runtime.chromium.launch_persistent_context.assert_not_called()
            context.new_page.assert_called_once()
            page.route.assert_called_once()
            client.close()

        # Closing the add-in's tab does NOT close Profile 3's context/window.
        page.close.assert_called_once()
        context.close.assert_not_called()
        browser.close.assert_called_once()
        runtime.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
