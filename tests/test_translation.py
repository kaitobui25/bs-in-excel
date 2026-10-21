"""Translation endpoint contracts without relying on Google network access."""
import unittest
from unittest.mock import Mock, patch

from text_browser.translation import translate_segments


class TranslationTests(unittest.TestCase):
    @patch("text_browser.translation.requests.get")
    def test_batch_preserves_order_and_uses_auto_detection(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = [["Hello", "ja"], ["Good morning", "vi"]]
        result = translate_segments(["こんにちは", "Chào buổi sáng"], "en")
        self.assertEqual(result, ["Hello", "Good morning"])
        params = get.call_args.kwargs["params"]
        self.assertEqual([value for key, value in params if key == "q"],
                         ["こんにちは", "Chào buổi sáng"])
        self.assertIn(("sl", "auto"), params)
        self.assertIn(("tl", "en"), params)

    @patch("text_browser.translation.requests.get")
    def test_invalid_requests_do_not_contact_provider(self, get):
        for texts, language in [([], "en"), ([""], "vi"), (["hello"], "fr"),
                                (["A" * 3801], "en"), (["x"] * 21, "vi")]:
            with self.subTest(texts=texts[:1], language=language):
                with self.assertRaises(ValueError):
                    translate_segments(texts, language)
        get.assert_not_called()

    @patch("text_browser.translation.requests.get")
    def test_unexpected_response_fails_without_partial_data(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = [["Only one", "en"]]
        with self.assertRaisesRegex(RuntimeError, "không hợp lệ"):
            translate_segments(["first", "second"], "vi")


if __name__ == "__main__":
    unittest.main()
