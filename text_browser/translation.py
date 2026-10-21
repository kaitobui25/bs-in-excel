"""Translate visible page text through Google's lightweight dictionary endpoint.

This endpoint is unofficial; callers must handle rate limits and failures.
Only the selected text is sent; browser cookies and session state are not used.
"""
from __future__ import annotations

from urllib.parse import quote

import requests

TRANSLATE_URL = "https://clients5.google.com/translate_a/t"
MAX_SEGMENTS = 20
MAX_CHARACTERS = 3800
MAX_ENCODED_CHARACTERS = 7200


def translate_segments(texts: list[str], target: str) -> list[str]:
    if target not in {"en", "vi"}:
        raise ValueError("Ngôn ngữ dịch không được hỗ trợ.")
    if (not isinstance(texts, list) or not 1 <= len(texts) <= MAX_SEGMENTS
            or any(not isinstance(text, str) or not text.strip() for text in texts)
            or sum(len(text) for text in texts) > MAX_CHARACTERS
            or sum(len(quote(text, safe="")) for text in texts) > MAX_ENCODED_CHARACTERS):
        raise ValueError("Nội dung dịch không hợp lệ hoặc quá dài.")

    try:
        response = requests.get(
            TRANSLATE_URL,
            params=[("client", "dict-chrome-ex"), ("sl", "auto"),
                    ("tl", target), *(('q', text) for text in texts)],
            timeout=9,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError("Google Translate không phản hồi. Hãy thử lại sau.") from exc

    if (not isinstance(result, list) or len(result) != len(texts)
            or any(not isinstance(entry, list) or not entry
                   or not isinstance(entry[0], str) for entry in result)):
        raise RuntimeError("Google Translate trả về dữ liệu không hợp lệ.")
    return [entry[0] for entry in result]
