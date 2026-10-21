"""Persistent reader word list, separate from version-controlled defaults.

Only keywords are user-editable. Matching rules remain in the bundled defaults
and are never overwritten by the settings UI. All operations are thread-safe.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unicodedata
from pathlib import Path


MAX_KEYWORDS = 1000
MAX_KEYWORD_LENGTH = 100


def _sort_key(word: str) -> tuple[str, str, str]:
    folded = "".join(
        char for char in unicodedata.normalize("NFKD", word)
        if not unicodedata.category(char).startswith("M")
    ).casefold().replace("đ", "d")
    return folded, word.casefold(), word


def normalize_keywords(value: object) -> list[str]:
    """Trim, deduplicate case-insensitively and sort for A-Z display."""
    if not isinstance(value, list) or len(value) > MAX_KEYWORDS:
        raise ValueError(f"Danh sách chỉ hỗ trợ tối đa {MAX_KEYWORDS} từ.")
    unique: dict[str, str] = {}
    for item in value:
        if not isinstance(item, str):
            raise ValueError("Mỗi dòng phải là một từ hoặc cụm từ.")
        word = item.strip()
        if not word:
            continue
        if (len(word) > MAX_KEYWORD_LENGTH or
                any(unicodedata.category(char) == "Cc" for char in word)):
            raise ValueError(f"Mỗi dòng phải có tối đa {MAX_KEYWORD_LENGTH} ký tự, không có ký tự điều khiển.")
        # Preserve the first spelling entered; don't merge accent variants that
        # people may deliberately keep (pokemon / Pokémon).
        unique.setdefault(unicodedata.normalize("NFKC", word).casefold(), word)
    return sorted(unique.values(), key=_sort_key)


class FilterSettingsStore:
    def __init__(self, defaults_path: Path, user_path: Path):
        self.defaults_path = defaults_path
        self.user_path = user_path
        self._lock = threading.RLock()

    def load(self) -> dict:
        with self._lock:
            defaults = json.loads(self.defaults_path.read_text(encoding="utf-8"))
            if not self.user_path.is_file():
                return {**defaults, "keywords": normalize_keywords(defaults["keywords"])}
            overrides = json.loads(self.user_path.read_text(encoding="utf-8"))
            if not isinstance(overrides, dict) or set(overrides) != {"keywords"}:
                raise ValueError("Dữ liệu danh sách lọc đã lưu không hợp lệ.")
            return {**defaults, "keywords": normalize_keywords(overrides["keywords"])}

    def save(self, keywords: object) -> dict:
        with self._lock:
            words = normalize_keywords(keywords)
            # Read defaults before writing, so broken source configuration
            # cannot create an unusable persisted list.
            defaults = json.loads(self.defaults_path.read_text(encoding="utf-8"))
            settings = {**defaults, "keywords": words}
            self.user_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.user_path.parent,
                    prefix=".sensitive-words-", suffix=".tmp", delete=False
                ) as output:
                    temp_path = Path(output.name)
                    json.dump({"keywords": words}, output, ensure_ascii=False, indent=2)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temp_path, self.user_path)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
            return settings
