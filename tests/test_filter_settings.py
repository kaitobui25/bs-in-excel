"""Persistence, canonical ordering and validation of user word lists."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from text_browser.filter_settings import FilterSettingsStore, normalize_keywords
from text_browser.service import WEB_ROOT


class FilterSettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.saved = Path(self.temp.name) / "settings" / "sensitive-words.json"
        self.store = FilterSettingsStore(WEB_ROOT / "sensitive-words.json", self.saved)

    def test_defaults_are_sorted_and_not_written_until_first_save(self):
        settings = self.store.load()
        self.assertIn("pokemon", settings["keywords"])
        self.assertIn("Pokémon", settings["keywords"])
        self.assertIn("center", settings["compoundSuffixes"])
        self.assertEqual(settings["keywords"], normalize_keywords(settings["keywords"]))
        self.assertFalse(self.saved.exists())

    def test_save_is_persistent_sorted_deduplicated_and_preserves_rules(self):
        result = self.store.save([" zoo ", "Pokémon", "alpha", "Nintendo", "alpha", "  ", "nintendo"])
        self.assertEqual(result["keywords"], ["alpha", "Nintendo", "Pokémon", "zoo"])
        self.assertEqual(result["mask"]["keepFirst"], 3)
        self.assertEqual(result["compoundSuffixes"], ["center", "switch"])
        self.assertEqual(json.loads(self.saved.read_text(encoding="utf-8")),
                         {"keywords": result["keywords"]})
        self.assertEqual(FilterSettingsStore(self.store.defaults_path, self.saved).load(), result)

    def test_empty_list_is_allowed_and_stays_empty(self):
        self.store.save([])
        self.assertEqual(self.store.load()["keywords"], [])

    def test_reject_invalid_values_without_destroying_existing_list(self):
        self.store.save(["good"])
        for value in (None, "good", [5], ["safe", "bad\nword"],
                      ["x" * 101], ["word"] * 1001):
            with self.subTest(value=repr(value)[:20]):
                with self.assertRaises(ValueError):
                    self.store.save(value)
                self.assertEqual(self.store.load()["keywords"], ["good"])

    def test_failed_atomic_replace_preserves_last_save_and_cleans_temp_files(self):
        self.store.save(["previous"])
        with patch("text_browser.filter_settings.os.replace", side_effect=OSError("read-only")):
            with self.assertRaises(OSError):
                self.store.save(["replacement"])
        self.assertEqual(self.store.load()["keywords"], ["previous"])
        self.assertEqual(list(self.saved.parent.glob("*.tmp")), [])

    def test_invalid_persisted_data_does_not_silently_restore_defaults(self):
        self.saved.parent.mkdir(parents=True)
        self.saved.write_text('{"unknown": true}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.load()

    def test_concurrent_saves_do_not_corrupt_file(self):
        threads = [threading.Thread(target=self.store.save, args=([f"keyword{n}"],))
                   for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.store.load()["keywords"]), 1)
