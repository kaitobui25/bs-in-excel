"""Pure command parsing: no Excel or browser dependencies."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode

_DOMAIN = re.compile(r"^(?:localhost(?::\d+)?|(?:[a-z0-9-]+\.)+[a-z0-9-]{2,})(?:[/:?#]|$)", re.I)
_COMMANDS = {":back", ":forward", ":reload", ":history", ":help"}


@dataclass(frozen=True)
class Command:
    action: str
    value: str = ""


def parse_command(raw: str) -> Command:
    value = (raw or "").strip()
    if not value:
        return Command("noop")
    lowered = value.lower()
    if lowered in _COMMANDS:
        return Command(lowered[1:])
    if lowered.startswith(":open "):
        number = lowered[6:].strip()
        if number.isdigit() and int(number) > 0:
            return Command("open_link", str(int(number)))
        return Command("invalid", "Dùng :open N (N là số liên kết).")
    if lowered.startswith(":"):
        return Command("invalid", f"Lệnh không hỗ trợ: {value}")
    if lowered.startswith(("https://", "http://")):
        return Command("navigate", value)
    if " " not in value and _DOMAIN.match(value):
        return Command("navigate", "https://" + value)
    return Command("search", value)


def google_search_url(query: str) -> str:
    return "https://www.google.com/search?" + urlencode({"q": query, "num": 10})
