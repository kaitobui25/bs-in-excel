"""Fast HTML-only browser for public web pages, with transparent search fallback."""
from __future__ import annotations

from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .browser import Link, PageData
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
        for tag in soup.select("script, style, noscript, svg, picture, img, video, audio, iframe, canvas"):
            tag.decompose()
        root = soup.select_one("main, [role='main'], article") or soup.body or soup
        for tag in root.select("nav, footer, aside"):
            tag.decompose()
        lines = [line.strip() for line in root.get_text("\n", strip=True).splitlines()]
        text = "\n".join(line for line in lines if line)
        links: list[Link] = []
        seen: set[str] = set()
        for anchor in root.select("a[href]"):
            url = urljoin(response.url, anchor.get("href", ""))
            if urlparse(url).scheme not in ("https", "http") or url in seen:
                continue
            name = anchor.get_text(" ", strip=True) or anchor.get("aria-label", "")
            if len(name) < 2:
                continue
            seen.add(url)
            links.append(Link(name[:130], url))
            if len(links) >= 90:
                break
        return PageData(title=title, url=response.url, text=text, links=links)

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
                title="Yahoo!検索 — kết quả dự phòng (Google hạn chế truy cập tự động)",
                url=alternate.url,
                text=("Google không cung cấp kết quả text cho yêu cầu tự động. "
                      "Các kết quả sau đến từ Yahoo!検索, KHÔNG phải Google.\n\n" + alternate.text),
                links=[Link("Mở Google trong trình duyệt ngoài", url)] + alternate.links,
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
