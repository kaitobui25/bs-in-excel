"""Attach to an already running Chrome via Chrome DevTools Protocol.

Only a new, dedicated tab is controlled. Existing tabs and browser settings
are not modified. No cookies, credentials, or browsing profiles are exported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from .config import CHROME_PORT_FILE, NAVIGATION_TIMEOUT_MS
from .navigation import google_search_url


@dataclass(frozen=True)
class Link:
    title: str
    url: str


@dataclass(frozen=True)
class PageData:
    title: str
    url: str
    text: str
    links: list[Link]
    blocks: list[dict] = field(default_factory=list)
    notice: str = ""


# Evaluate against the dedicated tab, returning JSON-compatible text only.
# Scripts on modern websites may still run INSIDE Chrome; never inside Excel.
EXTRACT_DOM = r"""
() => {
  const root = document.querySelector('main, [role="main"], article, #main') || document.body;
  if (!root) return { title: document.title, url: location.href, text: '', links: [] };
  const cleaned = (root.innerText || document.body.innerText || '')
    .split(/\n+/).map(line => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean).join('\n');
  const links = [];
  const seen = new Set();
  for (const node of root.querySelectorAll('a[href]')) {
    const href = node.href;
    if (!href || !/^https?:\/\//i.test(href) || seen.has(href)) continue;
    const name = (node.innerText || node.getAttribute('aria-label') || node.title || '')
      .replace(/\s+/g, ' ').trim();
    if (name.length < 2) continue;
    seen.add(href);
    links.push({title: name.slice(0, 130), url: href});
    if (links.length >= 90) break;
  }
  return {title: document.title || location.href, url: location.href,
          text: cleaned, links};
}
"""


def read_cdp_endpoint(port_file: Path = CHROME_PORT_FILE) -> str:
    parts = port_file.read_text(encoding="utf-8").splitlines()
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].startswith("/devtools/browser/"):
        raise ValueError("Chrome DevToolsActivePort không hợp lệ. Kiểm tra Remote Debugging.")
    return f"ws://127.0.0.1:{parts[0]}{parts[1]}"


class ChromeTextBrowser:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def connect(self) -> None:
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(
                read_cdp_endpoint(), timeout=25_000
            )
            if not self._browser.contexts:
                raise RuntimeError("Không tìm thấy Chrome context.")
            self._page = self._browser.contexts[0].new_page()
            self._page.route("**/*", self._route)
            self._page.set_default_timeout(NAVIGATION_TIMEOUT_MS)
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _route(route) -> None:
        # Route applies to the dedicated tab, never to other Profile 3 tabs.
        if route.request.resource_type in {"image", "media", "font"}:
            route.abort()
        else:
            route.continue_()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Chrome chưa kết nối.")
        return self._page

    def navigate(self, url: str) -> PageData:
        self.page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        # A small settling delay helps client-rendered pages without waiting for ads.
        self.page.wait_for_timeout(900)
        data = self.extract()
        if len(data.text) < 80:
            self.page.wait_for_timeout(1_200)
            data = self.extract()
        return data

    def search(self, query: str) -> PageData:
        return self.navigate(google_search_url(query))

    def back(self) -> PageData | None:
        response = self.page.go_back(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        return self.extract() if response is not None else None

    def forward(self) -> PageData | None:
        response = self.page.go_forward(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        return self.extract() if response is not None else None

    def reload(self) -> PageData:
        self.page.reload(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        return self.extract()

    def extract(self) -> PageData:
        info = self.page.evaluate(EXTRACT_DOM)
        return PageData(
            title=info["title"],
            url=info["url"],
            text=info["text"],
            links=[Link(item["title"], item["url"]) for item in info["links"]],
        )

    def close(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None
        if self._browser is not None:
            try:
                self._browser.close()  # Disconnects CDP; does not close Chrome itself.
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
