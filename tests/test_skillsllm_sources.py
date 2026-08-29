import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import skillsllm  # noqa: E402
from skillsllm_aihubmix import (  # noqa: E402
    AIHUBMIX_BLOG_URL,
    AIHUBMIX_CHANGELOG_URL,
    AIHUBMIX_DOCS_BLOG_URL,
    discover_aihubmix_docs_links,
    discover_aihubmix_links,
    parse_aihubmix_changelog,
)


class SkillsLlmExtraSourcesTests(unittest.TestCase):
    def test_xcmd_native_feed_is_registered(self):
        """x-cmd should use its native RSS feed."""
        urls = {source[1] for source in skillsllm.NATIVE_FEEDS}
        self.assertIn("https://www.x-cmd.com/feed.xml", urls)

    def test_aihubmix_sources_are_documented(self):
        """All requested AIHubMix surfaces should be exposed to source docs."""
        sources = set(skillsllm.doc_sources())
        self.assertIn(("AIHubMix Blog (PL)", AIHUBMIX_BLOG_URL), sources)
        self.assertIn(("AIHubMix Docs Blog (EN)", AIHUBMIX_DOCS_BLOG_URL), sources)
        self.assertIn(("AIHubMix Changelog", AIHUBMIX_CHANGELOG_URL), sources)

    def test_aihubmix_listing_discovers_only_polish_article_links(self):
        """Main-blog discovery should ignore tags, other hosts, and duplicates."""
        html = """
        <main>
          <a href="/blog/pl/first-post">First</a>
          <a href="https://aihubmix.com/blog/pl/second-post?ref=home">Second</a>
          <a href="/blog/pl/tag/news">News tag</a>
          <a href="https://example.com/blog/pl/external">External</a>
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

    def test_aihubmix_docs_listing_discovers_english_blog_articles(self):
        """Docs discovery should keep English blog pages only."""
        html = """
        <nav>
          <a href="/en/blogs/kimi-k3-guide">Kimi K3</a>
          <a href="/en/blogs/free-ai-models#intro">Free models</a>
          <a href="/cn/blogs/kimi-k3-guide">Chinese</a>
          <a href="https://example.com/en/blogs/external">External</a>
        </nav>
        """
        self.assertEqual(
            discover_aihubmix_docs_links(html),
            [
                "https://docs.aihubmix.com/en/blogs/kimi-k3-guide",
                "https://docs.aihubmix.com/en/blogs/free-ai-models",
            ],
        )

    def test_aihubmix_changelog_splits_dated_sections(self):
        """Each dated changelog section should become a stable feed entry."""
        html = """
        <main>
          <h3>2026 August 10</h3>
          <p>More complete cumulative usage for media generation.</p>
          <p>Improved Azure model-name compatibility.</p>
          <h3>2026 August 8</h3>
          <p>New video generation model.</p>
        </main>
        """
        entries = parse_aihubmix_changelog(html)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["link"], f"{AIHUBMIX_CHANGELOG_URL}#2026-08-10")
        self.assertEqual(entries[0]["source"], "AIHubMix Changelog")
        self.assertIn("cumulative usage", entries[0]["description"])


if __name__ == "__main__":
    unittest.main()
