"""Allow-list for page titles shown in the Excel reader.

Only edit TITLE_HOSTS to enable page titles for another trusted website.
Page content, section headings, authors, links and stored history are unaffected.
"""
from __future__ import annotations

from urllib.parse import urlparse


TITLE_HOSTS = ("siemens.com",)


def visible_title(url: str, title: str) -> str:
    """Show titles only for exact allowed domains and their subdomains.

    Match the final page URL, not the title text or the requested URL; this
    avoids spoofed Siemens titles on unrelated websites or redirect targets.
    """
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not title or not title.strip():
        return ""
    if any(hostname == host or hostname.endswith("." + host) for host in TITLE_HOSTS):
        return title
    return ""
