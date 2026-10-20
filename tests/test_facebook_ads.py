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

    def test_j_connect_sim_ad_from_excel_screenshot(self):
        ad = {
            "author": "J-Connect - Kết nối yêu thương",
            "text": (
                "CHỈ 2.000¥ CÓ NGAY COMBO 2 THÁNG SIM 100GB XOÁ TAN NỖI LO MẠNG LAG!\n"
                "Không thủ tục rườm rà, nhận SIM lắp vào máy là có mạng căng đét dùng ngay!\n"
                "Đặc quyền J-Connect: Cho mượn SIM miễn phí – Tuyệt đối không cọc\n"
                "Số lượng có hạn, chốt nhanh kẻo lỡ deal hời quốc dân anh em ơi!\n"
                "Inbox J-Connect lên đơn hỏa tốc, giao hàng tận tay mới cần thanh toán!\n"
                "MESSENGER\nSend message"
            ),
            "links": [{"title": "Send message", "url": "https://www.facebook.com/"}],
        }
        self.assertTrue(is_ad_post(ad))

    def test_flight_ad_without_cash_price_from_excel_screenshot(self):
        ad = {
            "author": "Phòng Vé Máy Bay - Travel’s One",
            "text": (
                "VÉ TẾT 2027 NHẬT BẢN ⇄ VIỆT NAM 2027!\n"
                "CỰC SỐC giảm ngay 30% cho vé khứ hồi khi đặt trong ngày hôm nay\n"
                "Nhiều hãng bay, linh hoạt ngày khởi hành\n"
                "Hỗ trợ đặt vé, đổi lịch theo điều kiện hãng\n"
                "Inbox để được tư vấn lịch bay & giá vé phù hợp See less\n"
                "MESSENGER\nSend message"
            ),
            "links": [{"title": "Phòng Vé Máy Bay", "url": "https://www.facebook.com/"}],
        }
        self.assertTrue(is_ad_post(ad))

    def test_mobi_jp_and_japanese_school_promotions(self):
        sim_ad = {
            "author": "Mobi JP",
            "text": (
                "Các gói SIM & WiFi cho mọi nhu cầu!\n"
                "MIỄN PHÍ 2 THÁNG + Dùng thử miễn phí 3 ngày\n"
                "Nhắn tin cho chúng tôi để biết thêm chi tiết!\n"
                "SIM Data • 100GB — ¥2,980/tháng\nPocket WiFi 5G"
            ),
        }
        school_ad = {
            "author": "Global Bridge Japan",
            "text": "ワーキングホリデーでも、保育のCertificate II資格が取れます。\nキャリアを目指しませんか？\nコースを2段階に分けることができます。",
            "links": [{"title": "More", "url": "https://www.global-bridge.com.au/"}],
        }
        self.assertTrue(is_ad_post(sim_ad))
        self.assertTrue(is_ad_post(school_ad))

    def test_global_bridge_childcare_course_from_screenshot(self):
        course_post = {
            "author": "Global Bridge Japan is in Australia.",
            "text": (
                "オーストラリアで保育士を目指す！チャイルドケア Certificate III 受講生募集中\n"
                "【対象】ワーキングホリデービザ（ワーホリ）の方\n"
                "観光ビザの方も！\n"
                "コース開始日はご自身の予定に合わせて調整可能！\n"
                "Certificate III取得で、時給アップを目指せます\n"
                "Certificate III取得者の時給の目安：約$40.59/時"
            ),
        }
        self.assertTrue(is_ad_post(course_post))

    def test_mtrend_business_promotion_from_screenshot(self):
        service_post = {
            "author": "Mtrend",
            "text": (
                "Chúng tôi luôn sẵn sàng hỗ trợ bạn!\n"
                "Chuyên cung cấp các dịch vụ di động dành cho người nước ngoài tại Nhật Bản.\n"
                "Tất cả các gói dịch vụ: www.mtrend.co.jp/all-plans-services See less\n"
                "0:00 / 0:00\nChat trên Messenger\nSend message"
            ),
            "pageCta": True,
            "links": [],
        }
        self.assertTrue(is_ad_post(service_post))
        # Plain website addresses in post text also count as external sites.
        self.assertTrue(is_ad_post({**service_post, "pageCta": False}))

    def test_scuba_shop_brand_story_from_chinese_screenshot(self):
        diving_shop = {
            "author": "黒潮潛水in沖縄 青洞浮潛/潜水・中文專門店 is at 黒潮潛水in沖縄",
            "text": (
                "【黑潮潛水的想法】\n"
                "我們不會因為你的證照等級高，就給你更高的評價。\n"
                "也不會因為你擅長業務銷售或社群媒體經營，就給你更高的評價。\n"
                "因為我們認為，僅憑這些條件很難真正判斷一位潛水教練的實力。"
            ),
        }
        self.assertTrue(is_ad_post(diving_shop))

    def test_brand_names_and_storytelling_alone_are_not_ads(self):
        for post in (
            {"author": "Global Bridge Japan", "text": "A lovely hike on Sunday with friends"},
            {"author": "Mtrend", "text": "A team photo from our staff picnic"},
            {"author": "Trần Văn A", "text": "Hôm nay kể chuyện đi lặn biển tại Okinawa cùng gia đình."},
            {"author": "Tình yêu du lịch", "text": "Đang nghiên cứu Certificate III và các khóa học bảo mẫu ở Úc."},
            {"author": "Mai", "text": "Bạn mình làm nghề lặn biển và hôm nay vừa đón con."},
            {"author": "My friend", "text": "Gửi tin nhắn cho mình để mình gửi ảnh họp lớp."},
        ):
            with self.subTest(post=post):
                self.assertFalse(is_ad_post(post))

    def test_japanese_mattress_brand_promotion_without_button(self):
        post = {
            "author": "NELL",
            "text": ("朝までの快眠を追求した、NELLマットレス。\n"
                     "寝返りのしやすさに拘った設計、マットレスの通気性。\n"
                     "120日間のフリートライアルでまずは体験してみてください。\n"
                     "NELL.LIFE"),
            "links": [{"title": "NELL.LIFE", "url": "https://l.facebook.com/l.php?u=https%3A%2F%2Fnell.life%2F"}],
        }
        self.assertTrue(is_ad_post(post))

    def test_dental_clinic_discount_ad_without_cash_price(self):
        post = {
            "author": "Nha Khoa Thẩm Mỹ Quốc Tế Win Smile - Hà Nội",
            "text": ("CHỈ 45 SUẤT – ƯU ĐÃI 45% RĂNG SỨ ORODENT\n"
                     "Dành tặng ưu đãi đặc biệt cho tất cả các dòng sứ Orodent.\n"
                     "Chỉ áp dụng cho 45 khách đăng ký sớm nhất! Inbox ngay giữ suất!"),
            "pageCta": True,
        }
        self.assertTrue(is_ad_post(post))

    def test_facebook_external_redirect_handled_only_when_commercial(self):
        self.assertFalse(is_ad_post({
            "author": "Bạn của tôi",
            "text": "Mình chia sẻ một bài báo về thời tiết Nhật Bản hôm nay.",
            "links": [{"title": "Read", "url": "https://l.facebook.com/l.php?u=https%3A%2F%2Fweather.example.com%2F"}],
        }))

    def test_ordinary_content_and_discussion_of_ads_is_retained(self):
        for content in (
            "Tôi đã mua wifi giá 2000 yên tháng trước và kể trải nghiệm sử dụng.",
            "Discuss why Sponsored posts can be misleading; examples below.",
            "Đăng ký lớp học cuối tuần và gặp gỡ các bạn, miễn phí.",
            "Giảm giá sản phẩm là vấn đề thị trường đang bàn luận.",
            "Tôi vừa đặt vé máy bay về quê, giá 2.000 yên và muốn chia sẻ trải nghiệm chuyến đi.",
            "Một công ty đang giảm 30% vé máy bay, theo bạn điều này có đáng tin không?",
            "Chuyện có ai ngờ: đứa chuyên cảnh báo mọi người cẩn thận kẻo bị lừa thì hôm nay bị mất 22 triệu.",
            "Tôi muốn bán cục 20g đã mua qua tay, vậy có phải đóng thuế gì không?",
        ):
            with self.subTest(text=content):
                self.assertFalse(is_ad_post({"text": content}))

    def test_noncommercial_author_with_sales_word_not_enough(self):
        self.assertFalse(is_ad_post({
            "author": "Bạn bè",
            "text": "Inbox mình để nhận ảnh miễn phí về buổi họp lớp nhé!",
        }))
        self.assertFalse(is_ad_post({
            "author": "Bản tin",
            "text": "Các hãng bay giảm giá 30% cho vé máy bay, nên cẩn thận khi mua.",
        }))


if __name__ == "__main__":
    unittest.main()
