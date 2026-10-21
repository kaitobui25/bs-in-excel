import unittest

from text_browser.facebook_ads import is_ad_post


class FacebookAdsTests(unittest.TestCase):
    def test_jewelry_page_slogan_without_price_or_sponsored_badge(self):
        self.assertTrue(is_ad_post({
            "author": "Moe モエ - Trang sức Bạc tại Japan",
            "text": "YOU’RE MY SUNSHINE – Vì em là ánh nắng của anh… See more",
            "links": [{"title": "Moe モエ", "url": "https://www.facebook.com/trangsucmoejp"}],
        }))

    def test_driving_school_residential_course_promotion(self):
        self.assertTrue(is_ad_post({
            "author": "VinaJapan Driving License Support",
            "text": (
                "GET YOUR JAPANESE DRIVER’S LICENSE – EASY, CONVENIENT & AFFORDABLE! "
                "Looking for a convenient way to get your Japanese driver’s license? "
                "Don’t miss our residential driving courses! Courses starting from only ¥230,000 "
                "Accommodation + 3 meals a day included. Study at a government-designated "
                "Japanese driving school. Practical training and testing conducted at the school. "
                "VINAJAPAN – Your trusted partner on the journey to getting a driver’s license in Japan."
            ),
        }))

    def test_personal_jewelry_or_driving_discussions_are_retained(self):
        for post in (
            {"author": "Moe", "text": "Hôm nay mình đi xem trang sức bạc cùng bạn bè."},
            {"author": "VinaJapan", "text": "Câu chuyện về cuộc sống ở Osaka cuối tuần."},
            {"author": "Bình", "text": "Mình đang học lái xe ở Nhật, nhiều trường có giá khoảng ¥230,000."},
        ):
            with self.subTest(post=post):
                self.assertFalse(is_ad_post(post))

    def test_chatgpt_japanese_free_trial_campaign(self):
        ad = {
            "author": "ChatGPT",
            "text": ("ChatGPT 画像で、自分をかわいいスタンプにしよう\n"
                     "1. クリックする\n2. 写真をアップロードする\n3. 友達に送る\n"
                     "CHATGPT.COM\nChatGPT 画像を無料で試そう"),
            "links": [{"title": "ChatGPT 画像を無料で試そう",
                       "url": "https://chatgpt.com/"}],
        }
        self.assertTrue(is_ad_post(ad))
        self.assertTrue(is_ad_post({**ad, "links": []}))

    def test_stylized_unicode_wifi_sales_campaign(self):
        ad = {
            "author": "Internet JAPAN - Giá Rẻ Mạng Khỏe",
            "text": ("𝑾𝑰𝑭𝑰 𝙘𝙤̂́ đ𝙞̣𝙣𝙝 𝙘𝙝𝙞̉ 1800 /𝙩𝙝𝙖́𝙣𝙜.\n"
                     "𝐓𝐨̂́𝐜 đ𝐨̣̂ 𝐟𝐮𝐥𝐥 𝐝𝐮𝐧𝐠 𝐥𝐮̛𝐨̛̣𝐧𝐠 5G\n"
                     "𝑴𝒊𝒆̂̃𝒏 𝒑𝒉𝒊́ 𝒍𝒂̆́𝒑 đ𝒂̣̆𝒕!\n"
                     "𝗟𝗶𝗲̂𝗻 𝗵𝗲̣̂ 𝘁𝗿𝘂̛̣𝗰 𝘁𝗶𝗲̂́𝗽 𝗙𝗮𝗻𝗽𝗮𝗴𝗲 đ𝗲̂̉ đ𝘂̛𝗼̛̣𝗰 𝘁𝘂̛ 𝘃𝗮̂́𝗻\n"
                     "𝗧𝗵𝗼̛̀𝗶 𝗴𝗶𝗮𝗻 𝗹𝗮̆́𝗽 đ𝗮̣̆𝘁 𝘁𝘂̛̀ 𝟮-𝟯 𝘁𝘂𝗮̂̀𝗻( 𝗶𝗯 𝗹𝗮̀ 𝗰𝗼́ 𝗪𝗜𝗙𝗜 )"),
            "pageCta": True,
        }
        self.assertTrue(is_ad_post(ad))
        self.assertTrue(is_ad_post({**ad, "pageCta": False}))

    def test_vat_vo_studio_branded_giveaway(self):
        self.assertTrue(is_ad_post({
            "author": "Vật Vờ Studio",
            "text": ("THỬ THÁCH: TINH MẮT TÌM MÁY, MAY MẮN RINH QUÀ\n"
                     "Khởi động Workshop Galaxy S26 FE - Mission Possible\n"
                     "THỂ LỆ THAM GIA CỰC DỄ:\n"
                     "Follow fanpage Vật Vờ Studio, Like và Share bài viết này về trang cá nhân "
                     "ở chế độ công khai kèm hashtag #thegioididong #Samsung #GalaxyS26FE.\n"
                     "Comment theo cú pháp: [Số chiếc Galaxy S26 FE] + [tag 2 người bạn]\n"
                     "PHẦN THƯỞNG:\nSamsung Galaxy Watch Fit3 dành cho người trả lời đúng nhất"),
        }))

    def test_property_listing_and_plugin_download_pitch_from_feed(self):
        self.assertTrue(is_ad_post({
            "author": "Trần Hoàng Thi Thiên",
            "text": ("Ra lô đất 574m2 thuộc khu phố Văn Hải, Phường Long Thành\n"
                     "Diện tích: 10 x 50, có 130m2 thổ cư\n"
                     "8 tỷ xxx (bớt chút cho khách)\n"
                     "Call: 0933.652.653 (Thiên để chốt)"),
        }))
        self.assertTrue(is_ad_post({
            "author": "Đạt Houzz",
            "text": ("Xưa bạn phải học rồi hì hục cả ngày mà chả ra gì "
                     "thì nay plugin này sẽ biến công việc đó như chơi game! "
                     "link tải plugin bình luận"),
        }))

    def test_brands_and_discussion_of_promotions_are_not_enough(self):
        for author, text in (
            ("ChatGPT", "Hôm nay nhóm chúng tôi thảo luận về an toàn AI và bảo mật thông tin."),
            ("Bạn học", "Mình dùng ChatGPT để soạn tài liệu, rất tiện."),
            ("Vật Vờ Studio", "Video đánh giá camera Galaxy, mình thích độ chi tiết."),
            ("Lan", "Tôi thấy mấy giveaway bắt follow và share rất phiền, nên cảnh giác."),
            ("Minh", "Tôi vừa mua WiFi và kể trải nghiệm dùng mạng ở Nhật Bản."),
            ("Hương", "Mình đang tìm link tải plugin của người bạn giới thiệu, ai biết chỉ giúp nhé."),
            ("Bình", "Tin tức thị trường: bán đất cần lưu ý giấy tờ và thuế, giá có thể hơn 8 tỷ."),
        ):
            with self.subTest(author=author, text=text):
                self.assertFalse(is_ad_post({"author": author, "text": text}))

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
