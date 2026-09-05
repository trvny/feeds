import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from huggingface import parse_posts, parse_trending_papers


class HuggingFacePostsTests(unittest.TestCase):
    def test_parse_posts_extracts_body_image_and_stable_link(self):
        html = """
        <article id="123">
          <a class="sr-only" href="/posts/alice/123">view post</a>
          <div class="text-smd/6 break-words">
            <span>A tiny model update</span><br>
            <span>Now with better evals.</span>
          </div>
          <img src="https://cdn-uploads.huggingface.co/demo.png">
        </article>
        """
        entries = parse_posts(html)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "A tiny model update")
        self.assertEqual(entries[0]["link"], "https://huggingface.co/posts/alice/123")
        self.assertIn("better evals", entries[0]["description"])
        self.assertEqual(
            entries[0]["image"], "https://cdn-uploads.huggingface.co/demo.png"
        )
        self.assertIsNone(entries[0]["date"])

    def test_parse_posts_skips_known_links(self):
        link = "https://huggingface.co/posts/alice/123"
        html = '<article id="123"><a href="/posts/alice/123">x</a></article>'
        self.assertEqual(parse_posts(html, {link}), [])


class HuggingFaceTrendingPapersTests(unittest.TestCase):
    def test_parse_trending_papers_extracts_metadata(self):
        html = """
        <article>
          <a href="/papers/2608.16157"><img
            src="https://cdn-thumbnails.huggingface.co/social-thumbnails/papers/2608.16157.png">
          </a>
          <h3>FreeToken: Efficient Edge-Native MoE Serving</h3>
          <p>Runs large open-weight models on personal machines.</p>
          <span>Published on Aug 17, 2026</span>
        </article>
        """
        entries = parse_trending_papers(html)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["link"], "https://huggingface.co/papers/2608.16157")
        self.assertEqual(entry["date"].date().isoformat(), "2026-08-17")
        self.assertIn("personal machines", entry["description"])
        self.assertIn("2608.16157.png", entry["image"])

    def test_parse_trending_papers_deduplicates_repeated_cards(self):
        card = """
        <article><a href="/papers/2608.1"></a><h3>Paper A</h3>
        <p>Summary</p><span>Aug 17, 2026</span></article>
        """
        self.assertEqual(len(parse_trending_papers(card + card)), 1)


if __name__ == "__main__":
    unittest.main()
