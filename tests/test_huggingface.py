import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from huggingface import parse_posts, parse_trending_papers


class HuggingFacePostsTests(unittest.TestCase):
    def test_parse_posts_extracts_body_image_date_and_canonical_link(self):
        html = """
        <article id="123">
          <a class="sr-only" href="/posts/alice/123/?ref=home">view post</a>
          <time datetime="2026-09-04T10:30:00Z">1 day ago</time>
          <div class="text-smd/6 break-words">
            <span>A tiny model update</span><br>
            <span>Now with better evals.</span>
          </div>
          <img src="https://cdn-uploads.huggingface.co/demo.png">
        </article>
        """
        entries = parse_posts(html)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["title"], "A tiny model update")
        self.assertEqual(entry["link"], "https://huggingface.co/posts/alice/123")
        self.assertEqual(entry["date"].isoformat(), "2026-09-04T10:30:00+00:00")
        self.assertIn("better evals", entry["description"])
        self.assertEqual(entry["image"], "https://cdn-uploads.huggingface.co/demo.png")

    def test_parse_posts_keeps_missing_source_date_unknown(self):
        html = '<article id="123"><a href="/posts/alice/123">x</a></article>'
        self.assertIsNone(parse_posts(html)[0]["date"])

    def test_parse_posts_skips_known_canonical_link(self):
        link = "https://huggingface.co/posts/alice/123"
        html = '<article id="123"><a href="/posts/alice/123/?foo=bar">x</a></article>'
        self.assertEqual(parse_posts(html, {link}), [])


class HuggingFaceTrendingPapersTests(unittest.TestCase):
    def test_parse_trending_papers_extracts_metadata(self):
        html = """
        <article>
          <a href="/papers/2608.16157/?ref=trending"><img
            src="https://cdn-thumbnails.huggingface.co/social-thumbnails/papers/2608.16157.png">
          </a>
          <h3>FreeToken: Efficient Edge-Native MoE Serving</h3>
          <p>Runs large open-weight models on personal machines.</p>
          <time datetime="2026-08-17">Published on Aug 17, 2026</time>
        </article>
        """
        entries = parse_trending_papers(html)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["link"], "https://huggingface.co/papers/2608.16157")
        self.assertEqual(entry["date"].date().isoformat(), "2026-08-17")
        self.assertIn("personal machines", entry["description"])
        self.assertIn("2608.16157.png", entry["image"])

    def test_parse_trending_papers_falls_back_to_visible_date(self):
        html = """
        <article><a href="/papers/2608.2"></a><h3>Paper B</h3>
        <p>Summary</p><span>Published on Aug 18, 2026</span></article>
        """
        self.assertEqual(
            parse_trending_papers(html)[0]["date"].date().isoformat(), "2026-08-18"
        )

    def test_parse_trending_papers_deduplicates_repeated_cards(self):
        card = """
        <article><a href="/papers/2608.1"></a><h3>Paper A</h3>
        <p>Summary</p><span>Aug 17, 2026</span></article>
        """
        self.assertEqual(len(parse_trending_papers(card + card)), 1)


if __name__ == "__main__":
    unittest.main()
