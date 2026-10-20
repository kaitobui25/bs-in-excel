"""Common page data and the optional full BrowserOS Neo reader."""
from __future__ import annotations

from dataclasses import dataclass, field
from .config import MAX_TEXT
from .neo_mcp import NeoPage
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
    has_more: bool = False


# Evaluate inside Neo; scripts never run in the Excel webview.
EXTRACT_DOM = r"""
() => {
  const root = document.querySelector('main, [role="main"], article, #main') || document.body;
  if (!root) return { title: document.title, url: location.href, text: '', links: [] };
  const cleaned = (root.innerText || document.body.innerText || '')
    .split(/\n+/).map(line => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean).join('\n').slice(0, __MAX_TEXT__);
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
""".replace("__MAX_TEXT__", str(MAX_TEXT))


READ_PAGE = f"""
let info = (await page.evaluate({EXTRACT_DOM}, undefined, {{maxChars: 200000}})).value;
if (!info) throw new Error('NEO_PAGE_RESULT_TOO_LARGE');
if (info.text.length < 80) {{
  await sleep(650);
  info = (await page.evaluate({EXTRACT_DOM}, undefined, {{maxChars: 200000}})).value;
  if (!info) throw new Error('NEO_PAGE_RESULT_TOO_LARGE');
}}
return info;
"""


class NeoTextBrowser:
    """Use one background Neo tab for JavaScript-rendered websites."""

    def __init__(self) -> None:
        self.page = NeoPage()

    def connect(self) -> None:
        # Opening a tab is delayed until the first URL is requested.
        pass

    @staticmethod
    def _to_page(info: dict) -> PageData:
        return PageData(title=info["title"], url=info["url"], text=info["text"],
                        links=[Link(link["title"], link["url"]) for link in info["links"]])

    def navigate(self, url: str) -> PageData:
        return self._to_page(self.page.run(READ_PAGE, url=url))

    def search(self, query: str) -> PageData:
        return self.navigate(google_search_url(query))

    def back(self) -> PageData | None:
        if self.page.page_id is None:
            return None
        info = self.page.run(f"""
const previous = (await page.info()).url;
await page.back();
if ((await page.info()).url === previous) return null;
{READ_PAGE}
""")
        return self._to_page(info) if info else None

    def forward(self) -> PageData | None:
        if self.page.page_id is None:
            return None
        info = self.page.run(f"""
const previous = (await page.info()).url;
await page.forward();
if ((await page.info()).url === previous) return null;
{READ_PAGE}
""")
        return self._to_page(info) if info else None

    def reload(self) -> PageData:
        return self._to_page(self.page.run(f"await page.reload();\n{READ_PAGE}"))

    def close(self) -> None:
        self.page.close()
