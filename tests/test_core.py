import tempfile
import unittest
from pathlib import Path

from text_browser.browser import Link, PageData, read_cdp_endpoint
from text_browser.excel_ui import page_rows
from text_browser.history import HistoryStore
from text_browser.navigation import google_search_url, parse_command


class NavigationTests(unittest.TestCase):
    def test_full_url(self):
        cmd = parse_command("https://www.siemens.com/ja-jp/products/tia-portal/")
        self.assertEqual((cmd.action, cmd.value), ("navigate", "https://www.siemens.com/ja-jp/products/tia-portal/"))

    def test_domain_without_scheme(self):
        self.assertEqual(parse_command("siemens.com").value, "https://siemens.com")

    def test_search(self):
        self.assertEqual(parse_command("siemens tia portal").action, "search")
        self.assertIn("q=siemens+tia+portal", google_search_url("siemens tia portal"))

    def test_commands(self):
        self.assertEqual(parse_command(":back").action, "back")
        self.assertEqual(parse_command(":history").action, "history")
        self.assertEqual(parse_command(":open 3").value, "3")
        self.assertEqual(parse_command(":open -2").action, "invalid")

    def test_invalid_command(self):
        self.assertEqual(parse_command(":rm").action, "invalid")


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


class RenderingTests(unittest.TestCase):
    def test_links_are_numbered_and_text_only(self):
        sample = PageData("Title", "https://siemens.com", "Hello\nworld",
                          [Link("Link A", "https://siemens.com/a")])
        rows, links = page_rows(sample)
        self.assertEqual(len(links), 1)
        self.assertIn(("1", "Link A", "https://siemens.com/a"), rows)
        self.assertTrue(any("Hello" in row[1] for row in rows))

    def test_cdp_endpoint_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "DevToolsActivePort"
            path.write_text("53859\n/devtools/browser/test-id\n", encoding="utf-8")
            self.assertEqual(read_cdp_endpoint(path), "ws://127.0.0.1:53859/devtools/browser/test-id")


if __name__ == "__main__":
    unittest.main()
