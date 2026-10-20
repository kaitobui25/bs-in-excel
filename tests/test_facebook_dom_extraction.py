"""Exercise the Facebook DOM extraction script against minimal post fixtures."""

import json
import shutil
import subprocess
import unittest

from text_browser.hybrid_browser import FACEBOOK_POSTS, MAX_POST_CHARS


@unittest.skipUnless(shutil.which("node"), "Node.js is required for DOM script tests")
class FacebookDomExtractionTests(unittest.TestCase):
    def test_body_excludes_obfuscated_header_but_keeps_real_text_and_links(self):
        script = r"""
const readPosts = __EXTRACT__;
const text = 'Chào cả nhà, mình chia sẻ kinh nghiệm vibe code một game nhập vai 2D.\nQUY MÔ GAME\n• Hai phe.';
const scrambled = 'ders tonoSplc9u6h60lgu'.split('').map(c => c + '\u034f').join('\n');
const messageLink = {
  href: 'https://example.com/guide', innerText: 'Tài liệu', textContent: 'Tài liệu',
  getClientRects: () => [{}], closest: () => null,
};
const previewLink = {
  href: 'https://example.com/story', innerText: 'Bài chia sẻ', textContent: 'Bài chia sẻ',
  getClientRects: () => [{}], closest: () => null,
};
const headerLink = {href: 'https://facebook.com/?__cft__=abc', innerText: scrambled, textContent: scrambled};
const message = {
  innerText: text,
  querySelectorAll: selector => selector === 'a[href]' ? [messageLink] : [],
};
const card = {
  innerText: 'Dương Bảo Ngọc ™️\n' + scrambled + '\n' + text,
  parentElement: null,
  getClientRects: () => [{}],
  closest: () => null,
  getAttribute: () => 'post-1',
  querySelector: selector => selector === '[data-ad-preview="message"]' ? message :
    selector === 'h3, h4' ? {innerText: 'Dương Bảo Ngọc ™️'} : null,
  querySelectorAll: selector => selector === '[data-ad-preview="message"]' ? [message] :
    selector === 'a[href]' ? [headerLink, messageLink, previewLink] : [],
};
const main = {
  contains: el => el === card,
  querySelectorAll: selector => selector === '[data-ad-preview="message"]' ? [message] : [],
};
message.parentElement = card;
card.parentElement = main;
globalThis.document = {
  querySelector: selector => selector === '[role="main"]' ? main : null,
  querySelectorAll: selector => selector === '[role="article"]' ? [card] : [],
};
globalThis.getComputedStyle = () => ({display: 'block', visibility: 'visible'});
const withMessage = readPosts();

// Older layouts without data-ad-preview must retain their fallback extraction.
main.querySelectorAll = () => [];
card.querySelector = selector => selector === 'h3, h4' ? {innerText: 'Dương Bảo Ngọc ™️'} : null;
card.querySelectorAll = selector => selector === 'a[href]' ? [messageLink] : [];
card.innerText = text;
const fallback = readPosts();
console.log(JSON.stringify({withMessage, fallback}));
""".replace("__EXTRACT__", FACEBOOK_POSTS.replace("__POST_LIMIT__", str(MAX_POST_CHARS)))
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, encoding="utf-8",
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["withMessage"]), 1)
        post = data["withMessage"][0]
        self.assertEqual(post["author"], "Dương Bảo Ngọc ™️")
        self.assertTrue(post["text"].startswith("Chào cả nhà"))
        self.assertIn("QUY MÔ GAME\n• Hai phe.", post["text"])
        self.assertNotIn("\u034f", post["text"])
        self.assertEqual(post["links"], [
            {"title": "Tài liệu", "url": "https://example.com/guide"},
            {"title": "Bài chia sẻ", "url": "https://example.com/story"},
        ])
        self.assertEqual(len(data["fallback"]), 1)
        self.assertEqual(data["fallback"][0]["text"], post["text"])


if __name__ == "__main__":
    unittest.main()
