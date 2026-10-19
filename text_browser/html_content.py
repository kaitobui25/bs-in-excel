"""Convert HTML to an ordered, safe text/link/image-placeholder representation.

No remote HTML or image bytes are sent to Excel. The original image positions
are represented by empty placeholders in the same reading flow.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from .browser import Link

SKIP_TAGS = {"script", "style", "noscript", "svg", "source", "video", "audio",
             "iframe", "canvas", "nav", "footer", "aside", "form", "input", "button"}
BLOCK_TAGS = {"p": "paragraph", "li": "item", "blockquote": "quote",
              "pre": "code", "tr": "paragraph", "figcaption": "caption",
              **{f"h{level}": "heading" for level in range(1, 7)}}
CONTAINER_TAGS = {"div", "section", "article", "header", "main", "ul", "ol", "table",
                  "figure"}
MAX_BLOCKS = 320
MAX_IMAGES = 90


def _url(href: str | None, base_url: str) -> str:
    if not href:
        return ""
    value = urljoin(base_url, href)
    return value if urlparse(value).scheme in ("http", "https") else ""


def extract_page(soup: BeautifulSoup, base_url: str) -> tuple[str, list[Link], list[dict]]:
    """Extract visible words and clickable links in reading order."""
    root = soup.select_one("main, [role='main'], article") or soup.body or soup
    blocks: list[dict] = []
    parts: list[dict] = []
    links: list[Link] = []
    seen: set[str] = set()
    image_count = 0

    def flush(kind: str = "paragraph") -> None:
        nonlocal parts
        if not parts:
            return
        # Avoid empty whitespace-only blocks.
        if all(p["type"] == "text" and not p["text"].strip() for p in parts):
            parts = []
            return
        if len(blocks) < MAX_BLOCKS:
            blocks.append({"kind": kind, "parts": parts})
        parts = []

    def append_text(text: str, href: str = "") -> None:
        value = re.sub(r"\s+", " ", text)
        if not value or (not parts and not value.strip()):
            return
        item_type = "link" if href else "text"
        if parts and parts[-1]["type"] == item_type and parts[-1].get("url", "") == href:
            parts[-1]["text"] += value
        else:
            item = {"type": item_type, "text": value}
            if href:
                item["url"] = href
            parts.append(item)

    def walk(node: Tag | NavigableString, href: str = "") -> None:
        nonlocal image_count
        if len(blocks) >= MAX_BLOCKS:
            return
        if isinstance(node, NavigableString):
            if str(node).strip() not in {"astro:end", "astro:start"}:
                append_text(str(node), href)
            return
        if not isinstance(node, Tag):
            return
        name = node.name or ""
        if name in SKIP_TAGS or node.has_attr("hidden") or node.get("aria-hidden") == "true":
            return
        style = (node.get("style") or "").replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            return
        if name in {"img", "image"}:
            width = str(node.get("width", "")).strip()
            height = str(node.get("height", "")).strip()
            if width.isdigit() and height.isdigit() and int(width) <= 2 and int(height) <= 2:
                return
            if image_count < MAX_IMAGES:
                item = {"type": "image"}
                if href:
                    item["url"] = href
                parts.append(item)
                image_count += 1
            return
        if name == "br":
            flush()
            return
        anchor_id = node.get("id")
        if anchor_id and isinstance(anchor_id, str) and len(anchor_id) < 160:
            flush()
            if len(blocks) < MAX_BLOCKS:
                blocks.append({"kind": "anchor", "id": anchor_id, "parts": []})
        if name == "a":
            target = _url(node.get("href"), base_url)
            label = node.get_text(" ", strip=True) or node.get("aria-label", "")
            if target and len(label.strip()) >= 2 and target not in seen:
                seen.add(target)
                links.append(Link(label.strip()[:130], target))
            for child in node.children:
                walk(child, target or href)
            return

        block_kind = BLOCK_TAGS.get(name)
        if block_kind or name in CONTAINER_TAGS:
            flush()
        for child in node.children:
            walk(child, href)
        if block_kind:
            flush(block_kind)
        elif name in CONTAINER_TAGS:
            flush()

    walk(root)
    flush()
    text = "\n".join(
        "".join(p.get("text", "") for p in block["parts"]).strip()
        for block in blocks
        if any(p.get("text", "").strip() for p in block["parts"])
    )
    return text, links, blocks
