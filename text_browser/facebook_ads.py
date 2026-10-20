"""Filter paid and organic sales promotions from Facebook text posts.

Facebook's sponsored label is not reliably present on ordinary page posts.
Use several independent *commercial intent* signals rather than requiring a
specific keyword trio. No content is sent to an external classification API.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qs, urlparse


_INVISIBLE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_LABEL = re.compile(
    r"^(?:sponsored|promoted|paid partnership|được tài trợ|quảng cáo|"
    r"đã tài trợ|広告|スポンサー|gesponsert|sponsorisé|patrocinado)$",
    re.IGNORECASE,
)
_SOLICIT = re.compile(
    r"(?<!\w)(?:inbox|ib|dm|send message|message us|shop now|buy now|order now|"
    r"contact us)(?!\w)|"
    r"nhắn\s*tin|gửi\s*tin\s*nhắn|liên\s*hệ\s*(?:ngay|để|với|bên)|"
    r"đăng\s*k[íý]\s*(?:ngay|hôm nay|wifi|sim)|mua\s*ngay|"
    r"chốt\s*(?:đơn|nhanh)|lên\s*đơn|"
    r"đặt\s*(?:vé|hàng|lịch)\s*(?:ngay|tại|qua|để)|hỗ\s*trợ\s*đặt\s*vé|"
    r"gọi\s*ngay|nhận\s*báo\s*giá|tư\s*vấn\s*(?:miễn\s*phí|ngay)|"
    r"đặt\s*mua|お申し込み|お申込み|お問い合わせ|資料請求|無料相談|"
    r"今すぐ|受講生募集|目指しませんか|申し込み受付|ご連絡ください",
    re.IGNORECASE,
)
_OFFER = re.compile(
    r"giảm\s*(?:ngay\s*)?(?:\d{1,3}\s*%|giá|cước|phí)|"
    r"ưu\s*đãi|khuyến\s*m[ạã]i|miễn\s*phí|tặng\s*(?:phí|thêm|ngay)|"
    r"không\s*(?:cần\s*)?(?:đặt\s*cọc|cọc|phí)|"
    r"(?<!\w)(?:combo|deal|sale|discount|limited offer|promotion|free trial|"
    r"special offer|\d{1,3}\s*%\s*off)(?!\w)|"
    r"chỉ\s*từ|giá\s*sốc|cực\s*sốc|siêu\s*tiết\s*kiệm|"
    r"dùng\s*thử\s*miễn\s*phí|割引|無料|キャンペーン|期間限定|特典|格安|"
    r"フリートライアル|お試し|返金保証",
    re.IGNORECASE,
)
_PRICE = re.compile(
    r"(?:\d[\d.,]*\s*(?:yên|円|yen|¥|₫|vnđ|đồng|usd|vnd)|"
    r"[¥$₫]\s*\d[\d.,]*|\d[\d.,]*\s*/\s*(?:tháng|month))",
    re.IGNORECASE,
)
_PRODUCT_OR_SERVICE = re.compile(
    r"(?<!\w)(?:sim|esim|wi-?fi|pocket wifi|tour|booking|flight|hotel|"
    r"data\s*(?:plan|sim)|visa)(?!\w)|"
    r"vé\s*(?:máy\s*bay|khứ\s*hồi|tết)|phòng\s*vé|"
    r"gói\s*(?:cước|mạng|dịch\s*vụ)|dịch\s*vụ|khách\s*sạn|"
    r"cước\s*(?:mạng|tháng)|giao\s*hàng|mỹ\s*phẩm|bảo\s*hiểm|"
    r"通販|留学|資格|コース|スクール|ビザ|保育|プログラム|"
    r"チャイルドケア|受講|certificate\s*[ivx]+|"
    r"潛水|潜水|浮潛|浮潜|ダイビング|スキューバ|教練|"
    r"移動通信|通信サービス|電信服務|電訊服務|"
    r"手機套餐|課程|招生|培訓|證照|"
    r"nha\s*khoa|răng\s*sứ|niềng\s*răng|thẩm\s*mỹ|"
    r"マットレス|寝具|ベッド|睡眠|歯科|美容",
    re.IGNORECASE,
)
_BUSINESS_AUTHOR = re.compile(
    r"phòng\s*vé|công\s*ty|dịch\s*vụ|cửa\s*hàng|trung\s*tâm|"
    r"học\s*viện|cửa\s*tiệm|nha\s*khoa|phòng\s*khám|thẩm\s*mỹ|"
    r"(?<!\w)(?:shop|store|agency|travel|tours|wifi|sim|airlines|"
    r"ltd|company|co\.,?\s*ltd|academy|school|training)(?!\w)|"
    r"株式会社|有限会社|公式ショップ|専門店|專門店|专门店|"
    r"旅行社|有限公司|學院|学院|補習班|培訓中心|"
    r"潛水|潜水|浮潛|浮潜|ダイビング",
    re.IGNORECASE,
)
_BUSINESS_PITCH = re.compile(
    r"chuyên\s*(?:cung\s*cấp|kinh\s*doanh|phân\s*phối|phục\s*vụ)|"
    r"chúng\s*tôi\s*(?:luôn\s*)?(?:sẵn\s*sàng\s*)?hỗ\s*trợ|"
    r"(?:toàn\s*bộ|tất\s*cả)\s*các\s*gói\s*dịch\s*vụ|"
    r"(?:提供|販売|販売中|受付中|開講中|受講生募集|受講者募集|"
    r"コース開始|資格取得|目指しましょう|招生中|開始招生|"
    r"課程招生|專業服務|專業教學|我們提供|"
    r"追求した|こだわった|体験してみてください|お試しください)",
    re.IGNORECASE,
)
_COURSE_RECRUITMENT = re.compile(
    r"(?:受講生|受講者|入学生|研修生)\s*募集(?:中)?|"
    r"(?:Certificate\s*[ivx]+|資格|保育士|留学|保育)\s*(?:受講|取得|コース|募集)|"
    r"(?:保育士|資格|スキル)\s*を?目指す|"
    r"(?:入学|受講|講座|コース)\s*(?:申込|申し込み|受付)|"
    r"(?:招生|報名|課程)\s*(?:開始|進行|招生中)",
    re.IGNORECASE,
)
_URGENCY = re.compile(
    r"số\s*lượng\s*có\s*hạn|chốt\s*nhanh|nhanh\s*tay|"
    r"không\s*bỏ\s*lỡ|trong\s*ngày\s*hôm\s*nay|"
    r"(?<!\w)(?:hurry|limited time|today only)(?!\w)|お早めに",
    re.IGNORECASE,
)
_MESSAGE_BUTTON = re.compile(
    r"^(?:messenger|send message|shop now|buy now|contact us|"
    r"gửi tin nhắn|nhắn tin|mua ngay|liên hệ|chat trên messenger|"
    r"メッセージを送信|傳送訊息|發送訊息)$",
    re.IGNORECASE,
)
_EXTERNAL_WEBSITE = re.compile(
    r"(?<![\w@])(?:(?:https?://)?www\.|https?://)?"
    r"(?:[a-z0-9-]+\.)+(?:com|net|org|jp|au|vn|life|edu|co\.jp)\b",
    re.IGNORECASE,
)
_TRIAL_CTA = re.compile(
    r"無料で?(?:試そう|試して|試す|体験|始めよう)|"
    r"(?:試そう|試して|体験).{0,15}無料|"
    r"try\s*(?:it\s*)?(?:for\s*)?free|start\s*(?:a\s*)?free\s*trial|"
    r"dùng\s*thử\s*miễn\s*phí",
    re.IGNORECASE,
)
_GIVEAWAY = re.compile(
    r"giveaway|give\s*away|(?:rinh|nhận|trúng)\s*quà|"
    r"phần\s*thưởng|giải\s*thưởng|quà\s*tặng|プレゼント企画",
    re.IGNORECASE,
)
_ENGAGEMENT = re.compile(
    r"(?<!\w)(?:follow|like|share|comment|tag)(?!\w)|"
    r"theo\s*dõi\s*fanpage|chia\s*sẻ\s*công\s*khai|gắn\s*thẻ",
    re.IGNORECASE,
)
_CAMPAIGN = re.compile(
    r"workshop|fanpage|hashtag|thể\s*lệ|khởi\s*động|"
    r"thử\s*thách|ra\s*mắt|sự\s*kiện|launch",
    re.IGNORECASE,
)
_PROPERTY_LISTING = re.compile(
    r"(?<!\w)(?:ra|bán|cần\s*bán)\s+(?:lô\s*)?(?:đất|nhà|căn\s*hộ)\b",
    re.IGNORECASE,
)
_CONTACT_PHONE = re.compile(r"\bcall\s*:\s*\+?\d|(?<!\d)(?:\d[\s.-]*){9,11}(?!\d)", re.IGNORECASE)
_DOWNLOAD_PROMO = re.compile(
    r"link\s*tải\s*(?:plugin|công\s*cụ|tool|app)\s*"
    r"(?:(?:ở|trong)\s*)?(?:bình\s*luận|comment|cmt)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Reveal stylized Unicode sales text for classification, not display."""
    return unicodedata.normalize("NFKC", _INVISIBLE.sub("", text))


def _is_external_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.hostname in {"l.facebook.com", "lm.facebook.com"}:
        # Facebook routes external links via l.facebook.com/l.php?u=...
        url = parse_qs(parsed.query).get("u", [url])[0]
    hostname = (urlparse(url).hostname or "").lower()
    return bool(hostname and not any(
        hostname == host or hostname.endswith("." + host)
        for host in ("facebook.com", "fb.com", "fb.watch")
    ))


def is_ad_post(post: dict) -> bool:
    """Detect clearly promotional posts; retain personal shopping discussions.

    A direct purchase/contact solicitation alone is not enough. Require
    supporting commercial evidence (service, price, business page or external
    store), so a friend's recipe, price comparison or scam warning is kept.
    """
    if post.get("sponsored") is True:
        return True
    text = _normalize(post.get("text", ""))
    if any(_LABEL.fullmatch(line.strip()) for line in text.splitlines()[:6]):
        return True

    author = _normalize(post.get("author", ""))
    links = post.get("links") or []
    solicitation = bool(_SOLICIT.search(text))
    offer = bool(_OFFER.search(text))
    price = bool(_PRICE.search(text))
    product = bool(_PRODUCT_OR_SERVICE.search(text))
    business = bool(_BUSINESS_AUTHOR.search(author))
    business_pitch = bool(_BUSINESS_PITCH.search(text))
    course_recruitment = bool(_COURSE_RECRUITMENT.search(text))
    urgency = bool(_URGENCY.search(text))
    external = any(_is_external_url(link.get("url", "")) for link in links) or any(
        _is_external_url(match.group(0) if match.group(0).lower().startswith("http")
                         else "https://" + match.group(0))
        for match in _EXTERNAL_WEBSITE.finditer(text)
    )
    message_button = post.get("pageCta") is True or any(
        _MESSAGE_BUTTON.fullmatch(_normalize(link.get("title", "")).strip()) for link in links
    )

    # Branded free trials and follow/share prize campaigns often have neither
    # a cash price nor a direct "buy" button (e.g. JP app ads, tech giveaways).
    if _TRIAL_CTA.search(text) and (external or business or product):
        return True
    if _GIVEAWAY.search(text) and _ENGAGEMENT.search(text) and _CAMPAIGN.search(text):
        return True
    if _PROPERTY_LISTING.search(text) and _CONTACT_PHONE.search(text):
        return True
    if _DOWNLOAD_PROMO.search(text):
        return True

    # Brand/shop posts can promote their services through storytelling rather
    # than prices or direct calls to action. A named specialist business whose
    # post concerns its own service is still commercial feed content.
    if business and (product or business_pitch or message_button):
        return True
    if course_recruitment and (product or business or business_pitch):
        return True
    if business_pitch and product and (message_button or external or business or offer):
        return True

    score = (3 * solicitation + 2 * offer + 2 * price + product
             + business + urgency + external + message_button + business_pitch)
    commercial_context = product or price or business or external
    # A direct solicitation pointing to an outside merchant can be an ad even
    # without a listed cash price or discount (common for course/travel posts).
    if solicitation and product and external and score >= 5:
        return True
    return bool(score >= 6 and commercial_context and (
        solicitation or (offer and (price or business or external))
    ))
