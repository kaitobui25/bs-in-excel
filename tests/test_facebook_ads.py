import unittest

from text_browser.facebook_ads import is_ad_post


class FacebookAdsTests(unittest.TestCase):
    def test_sponsored_metadata_multilingual(self):
        for text in ("Sponsored", "Được tài trợ", "Quảng cáo", "広告"):
            with self.subTest(text=text):
                self.assertTrue(is_ad_post({"text": f"My friend\n{text}\nWeekend photos"}))
        self.assertTrue(is_ad_post({"sponsored": True, "text": "Any content"}))

    def test_hachi_wifi_ad_without_explicit_label(self):
        content = ("HACHI 株式会社\nĐĂNG KÍ WIFI - GIẢM CƯỚC 24 THÁNG\n"
                   "CƯỚC GIẢM CHỈ TỪ 2000 yên/tháng\nKHÔNG CẦN GIẤY TỜ\nKHÔNG CẦN ĐẶT CỌC")
        self.assertTrue(is_ad_post({"text": content}))

    def test_ordinary_content_and_discussion_of_ads_is_retained(self):
        for content in (
            "Tôi đã mua wifi giá 2000 yên tháng trước và kể trải nghiệm sử dụng.",
            "Discuss why Sponsored posts can be misleading; examples below.",
            "Đăng ký lớp học cuối tuần và gặp gỡ các bạn, miễn phí.",
            "Giảm giá sản phẩm là vấn đề thị trường đang bàn luận.",
        ):
            with self.subTest(text=content):
                self.assertFalse(is_ad_post({"text": content}))


if __name__ == "__main__":
    unittest.main()
