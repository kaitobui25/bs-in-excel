"""Fast HTML-only browser for public web pages, with transparent search fallback."""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import CancelledError
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .browser import PageData
from .html_content import extract_page
from .navigation import google_search_url


class HttpTextBrowser:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155 Safari/537.36",
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8",
        })
        self.urls: list[str] = []
        self.position = -1

    def connect(self) -> None:
        """HTTP requires no browser startup or extra authorization."""

    @staticmethod
    def _extract(html: bytes, url: str) -> PageData:
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else url
        text, links, blocks = extract_page(soup, url)
        return PageData(title=title, url=url, text=text, links=links, blocks=blocks)

    def _fetch(self, url: str, on_progress: Callable[[PageData], None] | None = None,
               is_cancelled: Callable[[], bool] | None = None) -> PageData:
        # A partial HTML snapshot can be displayed while a slow response is
        # still downloading. Keep the final extraction identical to before.
        if on_progress is None:
            response = self.session.get(url, timeout=12)
            response.raise_for_status()
            if "html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Trang không phải HTML và không thể hiển thị dưới dạng text.")
            return self._extract(response.content, response.url)
        with self.session.get(url, timeout=(4, 12), stream=True) as response:
            response.raise_for_status()
            if "html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Trang không phải HTML và không thể hiển thị dưới dạng text.")
            html = bytearray()
            preview_attempts = 0
            for chunk in response.iter_content(chunk_size=16384):
                if is_cancelled and is_cancelled():
                    raise CancelledError()
                html.extend(chunk)
                if (on_progress and preview_attempts < 2
                        and len(html) >= (32768 if preview_attempts == 0 else 98304)):
                    preview_attempts += 1
                    preview = self._extract(bytes(html), response.url)
                    if len(preview.text) >= 120:
                        on_progress(preview)
                        on_progress = None  # One preview; never repeatedly rebuild the UI.
            return self._extract(bytes(html), response.url)

    def navigate(self, url: str) -> PageData:
        page = self._fetch(url)
        self.urls = self.urls[:self.position + 1] + [page.url]
        self.position += 1
        return page

    def search(self, query: str) -> PageData:
        url = google_search_url(query)
        page = self._fetch(url)
        if len(page.links) < 5 and ("Google Search" in page.title or len(page.text) < 240):
            alternate = self._fetch("https://search.yahoo.co.jp/search?p=" + quote_plus(query))
            page = PageData(
                title=f"Kết quả tìm kiếm: {query}",
                url=alternate.url,
                text=alternate.text,
                links=alternate.links,
                blocks=alternate.blocks,
            )
        self.urls = self.urls[:self.position + 1] + [page.url]
        self.position += 1
        return page

    def back(self) -> PageData | None:
        if self.position <= 0:
            return None
        page = self._fetch(self.urls[self.position - 1])
        self.position -= 1
        return page

    def forward(self) -> PageData | None:
        if self.position >= len(self.urls) - 1:
            return None
        page = self._fetch(self.urls[self.position + 1])
        self.position += 1
        return page

    def reload(self) -> PageData:
        if self.position < 0:
            raise ValueError("Chưa có trang để tải lại.")
        return self._fetch(self.urls[self.position])

    def close(self) -> None:
        self.session.close()
