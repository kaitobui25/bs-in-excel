"""Use the fast HTTP reader normally, real Chrome for JavaScript-only Facebook.

One dedicated Chrome profile is kept outside Git and reused for the entire
Excel add-in session. The user's existing Chrome profiles are untouched.
"""
from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from .browser import PageData
from .config import LOCAL_DATA, NAVIGATION_TIMEOUT_MS
from .html_content import extract_page
from .http_browser import HttpTextBrowser


def is_facebook_url(url: str) -> bool:
    """Match Facebook hosts, never domains that merely contain 'facebook.com'."""
    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    return hostname in {"facebook.com", "fb.com", "fb.watch"} or hostname.endswith(".facebook.com")


class FacebookChrome:
    """Lazy Playwright connection to one independent, persistent Chrome window."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @staticmethod
    def _route(route) -> None:
        if route.request.resource_type in {"image", "media", "font"}:
            route.abort()
        else:
            route.continue_()

    def _connect(self) -> None:
        if self._page is not None and not self._page.is_closed():
            return
        self._playwright = sync_playwright().start()
        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(LOCAL_DATA / "facebook-chrome-profile"),
                channel="chrome",
                headless=False,
                args=["--window-position=-30000,0", "--window-size=1000,740"],
                viewport={"width": 970, "height": 700},
                locale="ja-JP",
                timeout=15_000,
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._page.route("**/*", self._route)
            self._page.set_default_timeout(NAVIGATION_TIMEOUT_MS)
        except BaseException:
            self.close()
            raise

    def navigate(self, url: str) -> PageData:
        self._connect()
        assert self._page is not None
        self._page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        self._page.wait_for_timeout(1_100)
        soup = BeautifulSoup(self._page.content(), "lxml")
        text, links, blocks = extract_page(soup, self._page.url)
        # A signed-out session may only show Facebook's login wall. Do not try
        # to defeat authentication or claim private content was loaded.
        title = self._page.title() or self._page.url
        sign_in_wall = title == "Facebook" and self._page.locator('input[type="password"]').count() > 0
        return PageData(title=self._page.title() or self._page.url,
                        url=self._page.url, text=text, links=links, blocks=blocks,
                        notice=("Facebook yêu cầu đăng nhập để xem Bảng tin và nội dung riêng tư. "
                                "Bạn vẫn có thể mở các trang công khai bằng URL."
                                if sign_in_wall else ""))

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        finally:
            self._page = None
            self._context = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None


class HybridTextBrowser(HttpTextBrowser):
    """Keep one Back/Forward history across HTTP and Facebook's real Chrome."""

    def __init__(self) -> None:
        super().__init__()
        self._facebook: FacebookChrome | None = None

    def _fetch(self, url: str) -> PageData:
        if not is_facebook_url(url):
            return super()._fetch(url)
        if self._facebook is None:
            self._facebook = FacebookChrome()
        return self._facebook.navigate(url)

    def close(self) -> None:
        try:
            if self._facebook is not None:
                self._facebook.close()
                self._facebook = None
        finally:
            super().close()
