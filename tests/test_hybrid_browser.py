import unittest
from unittest.mock import Mock, patch

from text_browser.browser import PageData
from text_browser.hybrid_browser import FacebookNeo, HybridTextBrowser, MAX_FEED_POSTS, MAX_POST_CHARS, is_facebook_url
from text_browser.neo_mcp import NeoMcpError


def post(key, text, author="Author"):
    return {"key": key, "text": text, "author": author,
            "links": [{"title": "Read", "url": "https://www.facebook.com/posts/1"}]}


class HybridBrowserTests(unittest.TestCase):
    def test_facebook_hosts_only(self):
        for url in ("https://facebook.com/", "https://www.facebook.com/Siemens/",
                    "https://m.facebook.com/", "https://fb.watch/test", "https://fb.com/"):
            self.assertTrue(is_facebook_url(url), url)
        for url in ("https://notfacebook.com/", "https://facebook.com.example.org/",
                    "https://www.siemens.com/", "https://facebook.com.attacker.example/"):
            self.assertFalse(is_facebook_url(url), url)

    def test_facebook_is_lazy_and_reused(self):
        browser = HybridTextBrowser()
        fake = Mock()
        fake.navigate.side_effect = lambda url: PageData("Facebook", url, "public text", [])
        try:
            with patch("text_browser.hybrid_browser.FacebookNeo", return_value=fake) as factory, \
                 patch("text_browser.http_browser.HttpTextBrowser._fetch", autospec=True,
                       side_effect=lambda _self, url: PageData("Other", url, "normal HTML", [])):
                self.assertEqual(browser.navigate("https://www.siemens.com/").title, "Other")
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

    def test_feed_batches_are_combined_in_one_mcp_call(self):
        with patch("text_browser.hybrid_browser.NeoPage") as factory:
            page = factory.return_value
            page.page_id = 8
            page.run.side_effect = [True,
                {"title": "Facebook", "url": "https://www.facebook.com/", "posts": [
                    post("a", "First post with a meaningful body"),
                    post("b", "Another post with meaningful text"),
                    post("c", "A third post of adequate length"),
                    post("d", "A fourth post of adequate length"),
                    post("e", "A fifth post of adequate length")], "html": "", "signIn": False},
                {"title": "Facebook", "url": "https://www.facebook.com/", "posts": [
                    post("a", "First post with a meaningful body now expanded"),
                    post("f", "Sixth post with meaningful information"),
                    post("g", "Seventh post with meaningful information"),
                    post("h", "Eighth post with meaningful information"),
                    post("i", "Ninth post with meaningful information")], "html": "", "signIn": False},
            ]
            browser = FacebookNeo()
            first = browser.navigate("https://www.facebook.com/")
            self.assertEqual(len(first.blocks), 5)
            self.assertTrue(first.has_more)
            later = browser.load_more()
            self.assertEqual(len(later.blocks), 9)
            self.assertIn("expanded", later.text)
            self.assertEqual(page.run.call_count, 3)
            self.assertIn("await sleep(700)", page.run.call_args_list[1].args[0])
            self.assertIn("new Set([\"a\", \"b\", \"c\", \"d\", \"e\"])", page.run.call_args_list[2].args[0])
            browser.close()
            page.close.assert_called_once()

    def test_login_wall_and_public_page_fallback(self):
        with patch("text_browser.hybrid_browser.NeoPage") as factory:
            page = factory.return_value
            page.run.side_effect = [True, {
                "title": "Facebook", "url": "https://www.facebook.com/",
                "posts": [], "signIn": True,
                "html": "<main><p>Please log in</p><a href='/help'>Help</a></main>",
            }]
            browser = FacebookNeo()
            result = browser.navigate("https://www.facebook.com/")
            self.assertIn("BrowserOS Neo", result.notice)
            self.assertIn("Please log in", result.text)
            self.assertEqual(result.links[0].url, "https://www.facebook.com/help")
            browser.close()

    def test_feed_caps_total_posts_and_post_size(self):
        with patch("text_browser.hybrid_browser.NeoPage") as factory:
            page = factory.return_value
            page.run.side_effect = [True, {
                "title": "Facebook", "url": "https://www.facebook.com/", "signIn": False,
                "html": "", "posts": [post(str(i), "X" * (MAX_POST_CHARS + 400)) for i in range(90)],
            }]
            browser = FacebookNeo()
            result = browser.navigate("https://www.facebook.com/")
            self.assertEqual(len(result.blocks), MAX_FEED_POSTS)
            self.assertFalse(result.has_more)
            self.assertEqual(len(result.blocks[0]["parts"][0]["text"]), MAX_POST_CHARS)
            browser.close()

    def test_sponsored_and_price_promotion_removed_from_feed(self):
        with patch("text_browser.hybrid_browser.NeoPage") as factory:
            page = factory.return_value
            page.run.side_effect = [True, {
                "title": "Facebook", "url": "https://www.facebook.com/", "signIn": False,
                "html": "", "filteredAds": 1,
                "posts": [post("s", "A long sponsored card body", "Business") | {"sponsored": True},
                          post("ad2", "ĐĂNG KÍ WIFI - GIẢM CƯỚC 24 THÁNG 2000 yên/tháng"),
                          post("friend", "Today I met some good friends and went hiking")],
            }]
            browser = FacebookNeo()
            result = browser.navigate("https://www.facebook.com/Siemens/")
            self.assertEqual(len(result.blocks), 1)
            self.assertIn("hiking", result.text)
            self.assertNotIn("WIFI", result.text)
            browser.close()

    def test_ad_only_feed_does_not_fall_back_to_unfiltered_html(self):
        with patch("text_browser.hybrid_browser.NeoPage") as factory:
            page = factory.return_value
            page.run.side_effect = [True, {
                "title": "Facebook", "url": "https://www.facebook.com/", "signIn": False,
                "html": "<main>ĐĂNG KÍ WIFI - GIẢM CƯỚC 24 THÁNG</main>",
                "filteredAds": 1, "posts": [],
            }]
            browser = FacebookNeo()
            result = browser.navigate("https://www.facebook.com/Siemens/")
            self.assertEqual(result.text, "")
            self.assertEqual(result.blocks, [])
            self.assertIn("quảng cáo", result.notice)
            browser.close()

    def test_navigate_retries_when_session_lost_during_feed_read(self):
        with patch("text_browser.hybrid_browser.NeoPage") as factory:
            page = factory.return_value
            page.page_id = 12
            responses = iter([True, NeoMcpError("Session not found"), True,
                {"title": "Facebook", "url": "https://www.facebook.com/Siemens/",
                 "signIn": False, "html": "", "posts": [post("1", "A normal post with meaningful text about a regular activity")]}])
            def call(*args, **kwargs):
                value = next(responses)
                if isinstance(value, Exception):
                    page.page_id = None
                    raise value
                page.page_id = 13
                return value
            page.run.side_effect = call
            browser = FacebookNeo()
            result = browser.navigate("https://www.facebook.com/Siemens/")
            self.assertIn("normal post", result.text)
            self.assertEqual(page.run.call_count, 4)
            browser.close()


if __name__ == "__main__":
    unittest.main()
