"""Conservative, text-only filtering of Facebook sponsored feed cards.

Facebook does not publish a stable feed DOM. Prefer explicit sponsorship
metadata from the rendered page; use a narrow sales-copy fallback for ads
whose label is not exposed in text. No remote ad-blocking service is used.
"""
from __future__ import annotations

import re


_LABEL = re.compile(
    r"^(?:sponsored|promoted|paid partnership|được tài trợ|quảng cáo|"
    r"đã tài trợ|広告|スポンサー|gesponsert|sponsorisé|patrocinado)$",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"đăng\s*k[íý]|đặt hàng|mua ngay|liên hệ ngay|gọi ngay|"
    r"order now|sign up|subscribe now|shop now|buy now|今すぐ申し込",
    re.IGNORECASE,
)
_OFFER = re.compile(
    r"giảm\s*(?:giá|cước|phí|\d+\s*%)|ưu đãi|khuyến m[ạã]i|"
    r"không cần đặt cọc|discount|limited offer|promotion|\d+\s*%\s*off|割引",
    re.IGNORECASE,
)
_PRICE = re.compile(
    r"(?:\d[\d.,]*\s*(?:yên|円|yen|¥|₫|vnđ|đồng|usd|vnd)|"
    r"[¥$₫]\s*\d[\d.,]*|\d[\d.,]*\s*/\s*(?:tháng|month))",
    re.IGNORECASE,
)


def is_ad_post(post: dict) -> bool:
    """Exclude labelled ads and clear price+discount+sign-up promotions.

    Checking all three promotion signals avoids blocking everyday discussion
    of shopping, prices, or advertisements.
    """
    if post.get("sponsored") is True:
        return True
    text = post.get("text", "")
    if any(_LABEL.fullmatch(line.strip()) for line in text.splitlines()[:6]):
        return True
    return bool(_ACTION.search(text) and _OFFER.search(text) and _PRICE.search(text))
