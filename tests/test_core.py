import tempfile
import unittest
from pathlib import Path

from text_browser.history import HistoryStore
from text_browser.navigation import google_search_url


class SearchTests(unittest.TestCase):
    def test_google_search_encoding(self):
        self.assertIn("q=siemens+tia+portal", google_search_url("siemens tia portal"))


class HistoryTests(unittest.TestCase):
    def test_roundtrip_and_dedupe(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.json"
            history = HistoryStore(path)
            history.add("https://siemens.com/1", "One")
            history.add("https://siemens.com/2", "Two")
            history.add("https://siemens.com/1", "Updated")
            self.assertEqual([item.title for item in HistoryStore(path).entries], ["Updated", "Two"])

    def test_invalid_history_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.json"
            path.write_text("bad json", encoding="utf-8")
            self.assertEqual(HistoryStore(path).entries, [])


if __name__ == "__main__":
    unittest.main()
