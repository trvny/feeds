import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import skillsllm
from skillsllm_aihubmix import (
    AIHUBMIX_BLOG_URL,
    AIHUBMIX_CHANGELOG_LABEL,
    AIHUBMIX_DOCS_SOURCE,
    discover_aihubmix_docs_links,
    discover_aihubmix_links,
    discover_aihubmix_posts,
    parse_aihubmix_changelog,
)


class SkillsLlmExtraSourcesTests(unittest.TestCase):
    def test_xcmd_native_feed_is_registered(self):
        """x-cmd should use its native RSS feed."""
        urls = {source[1] for source in skillsllm.NATIVE_FEEDS}
        self.assertIn("https://www.x-cmd.com/feed.xml", urls)

    def test_agent_zero_articles_use_sitemap_discovery(self):
        """Agent Zero articles should reuse the generic dated-sitemap path."""
        source = [
            source
            for source in skillsllm.SOURCES
            if source["label"] == "Agent Zero Articles"
        ][0]
        self.assertEqual(source["sitemap"], "https://www.agent-zero.ai/sitemap.xml")
        self.assertTrue(source["use_lastmod"])
        self.assertTrue(source["include"]("https://www.agent-zero.ai/p/articles/a-zero2"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/docs/a-zero2"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/page/2/"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/tag/releases"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/?utm_source=sitemap"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/#latest"))

    def test_graphify_native_feeds_are_registered(self):
        """Graphify blog and changelog should use their native upstream feeds."""
        feeds = {source[0]: source[1] for source in skillsllm.NATIVE_FEEDS}
        self.assertEqual(feeds["Graphify Blog"], "https://graphify.com/feed.xml")
        self.assertEqual(
            feeds["Graphify Changelog"],
            "https://github.com/Graphify-Labs/graphify/releases.atom",
        )

    def test_aihubmix_sources_are_documented(self):
        """All requested AIHubMix surfaces should be exposed to source docs."""
        sources = dict(skillsllm.doc_sources())
        self.assertEqual(sources["AIHubMix Blog (PL)"], AIHUBMIX_BLOG_URL)
        self.assertEqual(
            sources[AIHUBMIX_DOCS_SOURCE["label"]],
            "https://docs.aihubmix.com/en/blogs",
        )
        self.assertEqual(
            sources[AIHUBMIX_CHANGELOG_LABEL],
            "https://docs.aihubmix.com/en/update/News",
        )

    def test_aihubmix_listing_discovers_only_polish_article_links(self):
        """Main-blog discovery should ignore tags, other hosts, and duplicates."""
        html = """
        <main>
          <div><a href="/blog/pl/first-post">First</a><span>20 sierpnia 2026</span></div>
          <div><a href="https://aihubmix.com/blog/pl/second-post?ref=home">Second</a><span>31 lipca 2026</span></div>
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
        posts = discover_aihubmix_posts(html)
        self.assertEqual(posts[0][1].isoformat(), "2026-08-20T00:00:00+00:00")
        self.assertEqual(posts[1][1].isoformat(), "2026-07-31T00:00:00+00:00")

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

    def test_aihubmix_changelog_splits_mintlify_year_and_day_blocks(self):
        """Mintlify's separate year and month/day text should form distinct entries."""
        html = """
        <main>
          <h3><a href="#"></a></h3>
          <p>2026</p>
          <p>August 10</p>
          <h4>More complete cumulative usage for media generation</h4>
          <p>Improved Azure model-name compatibility.</p>
          <h3><a href="#"></a></h3>
          <p>2026</p>
          <p>August 8</p>
          <h4>New video generation model</h4>
          <p>Added a new Seedance model.</p>
        </main>
        """
        entries = parse_aihubmix_changelog(html)
        changelog_url = dict(skillsllm.doc_sources())[AIHUBMIX_CHANGELOG_LABEL]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["link"], f"{changelog_url}#2026-08-10")
        self.assertEqual(entries[0]["source"], AIHUBMIX_CHANGELOG_LABEL)
        self.assertIn("cumulative usage", entries[0]["description"])
        self.assertEqual(entries[1]["link"], f"{changelog_url}#2026-08-08")
        self.assertNotIn("cumulative usage", entries[1]["description"])


if __name__ == "__main__":
    unittest.main()
