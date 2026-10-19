"""Fast HTML-only browser for public web pages, with transparent search fallback."""
from __future__ import annotations

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

    def _fetch(self, url: str) -> PageData:
        response = self.session.get(url, timeout=12)
        response.raise_for_status()
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("Trang không phải HTML và không thể hiển thị dưới dạng text.")
        soup = BeautifulSoup(response.content, "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else response.url
        text, links, blocks = extract_page(soup, response.url)
        return PageData(title=title, url=response.url, text=text, links=links, blocks=blocks)

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
