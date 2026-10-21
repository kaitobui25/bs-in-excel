"""Use fast HTTP for public pages and BrowserOS Neo for Facebook."""
from __future__ import annotations

import json
from collections.abc import Callable
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .browser import Link, PageData
from .config import LOCAL_DATA
from .facebook_ads import is_ad_post
from .html_content import extract_page
from .http_browser import HttpTextBrowser
from .neo_mcp import NeoMcpError, NeoPage


def is_facebook_url(url: str) -> bool:
    """Match Facebook hosts, never domains that merely contain 'facebook.com'."""
    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    return hostname in {"facebook.com", "fb.com", "fb.watch"} or hostname.endswith(".facebook.com")


# Read rendered Facebook posts instead of scraping React's hidden HTML markup.
# The script runs only in our BrowserOS Neo tab, never in Excel.
FACEBOOK_POSTS = r"""
() => {
  const visible = el => {
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' &&
      el.getClientRects().length > 0 && !el.closest('[aria-hidden="true"]');
  };
  const main = document.querySelector('[role="main"]') || document.querySelector('main');
  // Facebook's current home feed puts posts in message cards but keeps empty
  // role=article shells. Prefer each message card even when article shells exist.
  const messages = main ? [...main.querySelectorAll('[data-ad-preview="message"]')].slice(-18) : [];
  let candidates = messages.map(message => {
    let card = message;
    for (let parent = message.parentElement; parent && main.contains(parent); parent = parent.parentElement) {
      if (parent.querySelectorAll('[data-ad-preview="message"]').length !== 1) break;
      if (parent.querySelector('h3, h4')) {
        card = parent;
        break; // The nearest author header bounds this post; outer wrappers contain feed UI.
      }
    }
    return card;
  });
  if (!candidates.length) {
    const feed = document.querySelector('[role="feed"]');
    candidates = [...document.querySelectorAll('[role="article"]')].slice(-20);
    if (feed) candidates = candidates.filter(el => feed.contains(el));
    if (!candidates.some(el => (el.innerText || '').trim().length >= 35)) {
      candidates = [...document.querySelectorAll('[data-pagelet*="FeedUnit"]')].slice(-20);
    }
  }
  candidates = candidates.filter(el => visible(el) &&
    !candidates.some(other => other !== el && other.contains(el)));
  // Read the current end of the virtualized feed in bounded chunks.
  return candidates.slice(-12).map(el => {
    const label = /^(?:sponsored|promoted|paidpartnership|đượctàitrợ|quảngcáo|đãtàitrợ|広告|スポンサー|gesponsert|sponsorisé|patrocinado)$/iu;
    const message = el.querySelector('[data-ad-preview="message"]');
    const sponsor = [...el.querySelectorAll('[aria-label], [title], a, span')].slice(0, 280)
      .some(node => {
        if (message && !(message.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_PRECEDING)) return false;
        const names = [node.getAttribute('aria-label'), node.getAttribute('title'), node.innerText];
        return names.some(name => name && label.test(name.replace(/[\s\u200b-\u200f\ufeff]/g, '')));
      }) || [...el.querySelectorAll('a[href]')].some(a => /facebook\.com\/(?:ads\/about|about\/ads)\b/i.test(a.href));
    // Sales CTAs are attached to Facebook Page cards, not necessarily to a
    // clickable <a> link; pass their presence to the local text classifier.
    const pageCta = [...el.querySelectorAll('button, [role="button"], a')].some(node => {
      const label = (node.getAttribute('aria-label') || node.innerText || '').trim();
      return /^(?:send message|contact us|shop now|buy now|visit website|book now|call now|gửi tin nhắn|nhắn tin|liên hệ|mua ngay|メッセージを送信|傳送訊息|發送訊息)$/iu.test(label);
    });
    const author = (el.querySelector('h3, h4')?.innerText || '').split('\n')[0].trim().slice(0, 120);
    // The card header contains a Facebook-generated timestamp link whose
    // characters are individually positioned (and can include U+034F).
    // Read the actual post body instead of flattening that header into text.
    const text = ((message || el).innerText || '')
      .replace(/[\u200b-\u200f\ufeff]/g, '')
      .split(/\n+/).map(line => line.trim())
      .filter(line => line && line !== 'Facebook' && !/^[\s$\/|·•]+$/.test(line))
      .join('\n')
      .replace(/\s+(?:See less|Xem bớt|Thu gọn)\s*$/iu, '');
    const links = [];
    const seen = new Set();
    for (const a of el.querySelectorAll('a[href]')) {
      // Ignore the obfuscated timestamp link, but retain links in previews
      // outside the message body (for example, shared article cards).
      if (((a.textContent || '').match(/\u034f/g) || []).length >= 10) continue;
      if (!visible(a) || !/^https?:\/\//i.test(a.href) || seen.has(a.href)) continue;
      const title = (a.innerText || a.getAttribute('aria-label') || '').trim();
      if (title.length < 2) continue;
      seen.add(a.href);
      links.push({title: title.slice(0, 100), url: a.href});
      if (links.length >= 12) break;
    }
    // Permalinks can exist on visually hidden timestamp anchors.
    const permalink = [...el.querySelectorAll('a[href]')].map(a => a.href)
      .find(url => /\/(posts|permalink|videos|reel)\/|story\.php|\/photo\//.test(url));
    const feedId = el.closest('[data-pagelet*="FeedUnit"]')?.getAttribute('data-pagelet') ||
      el.getAttribute('data-id') || '';
    const lead = text.slice(0, 32).replace(/(?:See more|Xem thêm|もっと見る)$/i, '').trim();
    return {key: permalink || `${feedId}:${author}:${lead}`, author,
            text: text.slice(0, __POST_LIMIT__), links, sponsored: sponsor, pageCta};
  }).filter(post => post.text.length >= 35);
}
"""

FACEBOOK_EXPAND = r"""
() => {
  let expanded = 0;
  const buttons = [...document.querySelectorAll('[role="article"] [role="button"], [data-pagelet*="FeedUnit"] [role="button"], [data-ad-preview="message"] span, [data-ad-preview="message"] [role="button"]')].slice(-120);
  for (const button of buttons) {
    if (expanded >= 8) break;
    const label = (button.innerText || '').trim();
    if (/^(?:…\s*)?(See more|Xem thêm|もっと見る)$/i.test(label)) {
      (button.closest('[role="button"]') || button).click();
      expanded++;
    }
  }
  return expanded;
}
"""

MAX_FEED_POSTS = 80
MAX_POST_CHARS = 3_500


class FacebookNeo:
    """Extract posts from a single Neo tab without touching existing tabs."""

    def __init__(self) -> None:
        self._page = NeoPage(block_media=True,
                             tab_store=LOCAL_DATA / "neo-facebook-tab.json",
                             reuse_hosts=("facebook.com", "fb.com", "fb.watch"))
        self._posts: dict[str, dict] = {}
        self._rejected_keys: set[str] = set()
        self._ads_filtered = 0
        self._scan_timed_out = False
        self._url = ""
        self._title = "Facebook"

    def navigate(self, url: str, on_progress: Callable[[PageData], None] | None = None) -> PageData:
        is_feed = urlparse(url).path in {"", "/"}
        # Navigation can be slow on Facebook. Keep it separate from scrolling
        # so no single Neo run spends its entire 30s budget on both.
        for attempt in range(2):
            self._posts.clear()
            self._rejected_keys.clear()
            self._ads_filtered = 0
            self._scan_timed_out = False
            try:
                self._page.run("return true;", url=url)
                info = self._gather_posts(5 if is_feed else 1, 6 if is_feed else 0,
                                          on_progress=on_progress)
                break
            except NeoMcpError:
                # The first navigate run may succeed but the MCP session can
                # expire before the feed read. Retry only if the old tab was
                # actually lost; a timeout or extraction error is not safe to
                # replay automatically.
                if attempt or self._page.page_id is not None:
                    raise
        if self._posts:
            return self._feed_page(notice=self._timeout_notice() if self._scan_timed_out else "")
        if self._ads_filtered:
            return PageData(title=self._title, url=self._url, text="", links=[], blocks=[],
                            notice="Đã ẩn bài viết quảng cáo; chưa có bài thông thường để hiển thị.")
        soup = BeautifulSoup(info.get("html", ""), "lxml")
        text, links, blocks = extract_page(soup, self._url)
        return PageData(title=self._title, url=self._url, text=text, links=links,
                        blocks=blocks, notice=(
                            "Facebook yêu cầu đăng nhập trong BrowserOS Neo để xem Bảng tin. "
                            "Bạn vẫn có thể mở các trang công khai bằng URL."
                            if info.get("signIn") else ""))

    def _gather_posts(self, new_posts: int, scrolls: int,
                      on_progress: Callable[[PageData], None] | None = None) -> dict:
        # Each bounded run scrolls at most once. Stop when the goal is met,
        # at the login wall, or after the requested scroll budget.
        remaining = scrolls
        self._scan_timed_out = False
        before = len(self._posts)
        previous = tuple((key, hash(post["text"])) for key, post in self._posts.items())
        first = True
        while True:
            # First read without scrolling: emit available posts before doing
            # the slower multi-scroll feed scan.
            chunk = 0 if first and on_progress else min(remaining, 1)
            first = False
            try:
                info = self._collect_feed(max(1, new_posts - (len(self._posts) - before)), chunk)
            except NeoMcpError as exc:
                # Neo hard-caps each run at 30 seconds. Keep already validated
                # posts if a later scan times out instead of discarding them.
                if self._posts and "run exceeded 30000ms" in str(exc).lower():
                    self._scan_timed_out = True
                    return {"title": self._title, "url": self._url, "signIn": False, "html": ""}
                raise
            snapshot = tuple((key, hash(post["text"])) for key, post in self._posts.items())
            if on_progress and snapshot and snapshot != previous:
                on_progress(self._feed_page())
            previous = snapshot
            if len(self._posts) - before >= new_posts or info.get("signIn") or remaining <= chunk:
                return info
            remaining -= chunk

    def _collect_feed(self, min_posts: int, scrolls: int, url: str | None = None) -> dict:
        # One MCP call for all batches of DOM extraction/scrolling. A 30s run
        # limit applies; stop as soon as enough new posts have been found.
        script = """
const existing = new Set(__EXISTING__);
const rejected = new Set(__REJECTED__);
const found = new Map();
let filteredAds = 0;
for (let index = 0; index <= __SCROLLS__; index++) {
  const expanded = (await page.evaluate(__EXPAND__)).value;
  if (expanded) await sleep(150);
  const posts = (await page.evaluate(__POSTS__, undefined, {maxChars: 200000})).value;
  if (!Array.isArray(posts)) throw new Error('NEO_FACEBOOK_RESULT_TOO_LARGE');
  for (const post of posts) {
    if (!post.key || rejected.has(post.key)) continue;
    if (post.sponsored) { rejected.add(post.key); filteredAds++; continue; }
    const old = found.get(post.key);
    if (!old || post.text.length > old.text.length) found.set(post.key, post);
  }
  const newCount = [...found.keys()].filter(key => !existing.has(key)).length;
  if (newCount >= __TARGET__ || newCount + existing.size >= __LIMIT__ || index === __SCROLLS__) break;
  await page.evaluate(() => window.scrollBy(0, Math.max(innerHeight * 0.85, 650)));
  await sleep(700);
}
const meta = (await page.evaluate(() => ({
  title: document.title || location.href,
  url: location.href,
  signIn: !!document.querySelector('input[type="password"]')
}))).value;
const html = (found.size || rejected.size) ? '' : (await page.evaluate(() =>
  (document.querySelector('main, [role="main"]') || document.body)?.outerHTML.slice(0, 120000) || ''
, undefined, {maxChars: 200000})).value;
if (html === undefined) throw new Error('NEO_FACEBOOK_HTML_TOO_LARGE');
return { ...meta, html, filteredAds, rejectedKeys: [...rejected],
         posts: [...found.values()].slice(0, __LIMIT__) };
"""
        replacements = {
            "__EXISTING__": json.dumps(list(self._posts), ensure_ascii=False),
            "__REJECTED__": json.dumps(list(self._rejected_keys), ensure_ascii=False),
            "__SCROLLS__": str(scrolls),
            "__EXPAND__": FACEBOOK_EXPAND,
            "__POSTS__": FACEBOOK_POSTS.replace("__POST_LIMIT__", str(MAX_POST_CHARS)),
            "__TARGET__": str(min_posts),
            "__LIMIT__": str(MAX_FEED_POSTS),
        }
        for key, value in replacements.items():
            script = script.replace(key, value)
        info = self._page.run(script, url=url)
        self._url = info["url"]
        self._title = info["title"]
        self._ads_filtered += info.get("filteredAds", 0)
        self._rejected_keys.update(info.get("rejectedKeys", []))
        for post in info["posts"]:
            if is_ad_post(post):
                key = post.get("key")
                if key not in self._rejected_keys:
                    self._ads_filtered += 1
                if key:
                    self._rejected_keys.add(key)
                    self._posts.pop(key, None)
                continue
            key = post.get("key")
            if not key or (key not in self._posts and len(self._posts) >= MAX_FEED_POSTS):
                continue
            post["text"] = post["text"][:MAX_POST_CHARS]
            previous = self._posts.get(key)
            if previous is None or len(post["text"]) > len(previous["text"]):
                self._posts[key] = post
        return info

    @staticmethod
    def _timeout_notice() -> str:
        return "BrowserOS Neo phản hồi chậm. Đã giữ các bài đã tải; hãy thử Tải thêm bài viết."

    def _feed_page(self, notice: str = "") -> PageData:
        blocks = []
        links = []
        for key, post in self._posts.items():
            parts = [{"type": "text", "text": post["text"]}]
            for link in post["links"]:
                if not link["url"].startswith(("https://", "http://")):
                    continue
                parts.append({"type": "link", "text": link["title"], "url": link["url"]})
                links.append(Link(link["title"], link["url"]))
            blocks.append({"kind": "post", "key": key,
                           "author": post.get("author", ""), "parts": parts})
        text = "\n\n".join(post["text"] for post in self._posts.values())
        if not blocks:
            notice = ("Chưa lấy được bài viết từ Bảng tin. Hãy đăng nhập Facebook "
                      "trong BrowserOS Neo, rồi bấm Tải lại.")
        return PageData(title=self._title, url=self._url,
                        text=text, links=links, blocks=blocks, notice=notice,
                        has_more=bool(blocks) and len(blocks) < MAX_FEED_POSTS)

    def load_more(self, on_progress: Callable[[PageData], None] | None = None) -> PageData:
        if self._page.page_id is None or not self._posts:
            raise ValueError("Chưa có Bảng tin Facebook để tải thêm.")
        before = len(self._posts)
        self._gather_posts(new_posts=min(4, MAX_FEED_POSTS - before), scrolls=6,
                           on_progress=on_progress)
        note = (self._timeout_notice() if self._scan_timed_out else
                "Không tìm thấy bài mới. Hãy thử tải lại Bảng tin." if len(self._posts) == before else "")
        return self._feed_page(notice=note)

    def close(self) -> None:
        self._page.close()
        self._posts.clear()
        self._rejected_keys.clear()


class HybridTextBrowser(HttpTextBrowser):
    """Keep one Back/Forward history across HTTP pages and Facebook in Neo."""

    def __init__(self) -> None:
        super().__init__()
        self._facebook: FacebookNeo | None = None

    def _fetch(self, url: str) -> PageData:
        if not is_facebook_url(url):
            return super()._fetch(url)
        if self._facebook is None:
            self._facebook = FacebookNeo()
        return self._facebook.navigate(url)

    def load_more(self) -> PageData:
        if self.position < 0 or not is_facebook_url(self.urls[self.position]) or self._facebook is None:
            raise ValueError("Tải thêm chỉ áp dụng cho trang Facebook đang mở.")
        return self._facebook.load_more()

    def close(self) -> None:
        try:
            if self._facebook is not None:
                self._facebook.close()
                self._facebook = None
        finally:
            super().close()
