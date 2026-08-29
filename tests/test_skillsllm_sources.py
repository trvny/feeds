import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import skillsllm  # noqa: E402
from skillsllm_aihubmix import (  # noqa: E402
    AIHUBMIX_BLOG_URL,
    discover_aihubmix_links,
)


class SkillsLlmExtraSourcesTests(unittest.TestCase):
    def test_xcmd_native_feed_is_registered(self):
        urls = {source[1] for source in skillsllm.NATIVE_FEEDS}
        self.assertIn("https://www.x-cmd.com/feed.xml", urls)

    def test_aihubmix_polish_blog_is_documented(self):
        self.assertIn(("AIHubMix Blog (PL)", AIHUBMIX_BLOG_URL), skillsllm.doc_sources())

    def test_aihubmix_listing_discovers_only_polish_article_links(self):
        html = """
        <main>
          <a href="/blog/pl/first-post">First</a>
          <a href="https://aihubmix.com/blog/pl/second-post?ref=home">Second</a>
          <a href="/blog/pl/tag/news">News tag</a>
          <a href="/blog/english-post">English</a>
          <a href="/blog/pl/first-post#more">Duplicate</a>
        </main>
        """
        self.assertEqual(
            discover_aihubmix_links(html),
            [
                "https://aihubmix.com/blog/pl/first-post",
                "https://aihubmix.com/blog/pl/second-post",
            ],
        )


if __name__ == "__main__":
    unittest.main()
