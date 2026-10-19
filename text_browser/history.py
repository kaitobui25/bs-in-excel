"""Recent browsing history stored outside the Git repository."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import MAX_HISTORY


@dataclass(frozen=True)
class HistoryEntry:
    url: str
    title: str
    visited_at: str


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path
        self.entries = self._load()

    def _load(self) -> list[HistoryEntry]:
        if not self.path.is_file():
            return []
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
            return [
                HistoryEntry(str(r["url"]), str(r["title"]), str(r["visited_at"]))
                for r in records[:MAX_HISTORY]
            ]
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def add(self, url: str, title: str) -> None:
        if not url.startswith(("https://", "http://")):
            return
        entry = HistoryEntry(url, title, datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self.entries = [entry] + [e for e in self.entries if e.url != url]
        self.entries = self.entries[:MAX_HISTORY]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement avoids a half-written history after interruption.
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps([asdict(e) for e in self.entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp, self.path)
