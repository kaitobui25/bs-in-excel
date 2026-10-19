"""Pure Google search URL helper (no browser or Excel dependencies)."""
from __future__ import annotations

from urllib.parse import urlencode


def google_search_url(query: str) -> str:
    return "https://www.google.com/search?" + urlencode({"q": query, "num": 10})
