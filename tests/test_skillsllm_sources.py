import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import saas
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
        sources = {source["label"]: source for source in skillsllm.SOURCES}
        self.assertIn("Agent Zero Articles", sources)
        source = sources["Agent Zero Articles"]
        self.assertEqual(source["sitemap"], "https://www.agent-zero.ai/sitemap.xml")
        self.assertTrue(source["use_lastmod"])
        self.assertTrue(source["include"]("https://www.agent-zero.ai/p/articles/a-zero2"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/docs/a-zero2"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/page/2/"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/tag/releases"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/?utm_source=sitemap"))
        self.assertFalse(source["include"]("https://www.agent-zero.ai/p/articles/#latest"))

    def test_otterly_and_longato_use_post_sitemaps(self):
        """GEO/LLM blogs without RSS should use their dated Yoast post sitemaps."""
        sources = {source["label"]: source for source in skillsllm.SOURCES}

        otterly = sources["OtterlyAI Blog"]
        self.assertEqual(
            otterly["sitemap"], "https://otterly.ai/blog/post-sitemap.xml"
        )
        self.assertTrue(
            otterly["include"]("https://otterly.ai/blog/is-geo-replacing-seo/")
        )
        self.assertFalse(otterly["include"]("https://otterly.ai/blog/"))

        longato = sources["Flavio Longato"]
        self.assertEqual(
            longato["sitemap"], "https://www.longato.ch/post-sitemap.xml"
        )
        self.assertTrue(
            longato["include"]("https://www.longato.ch/llmstxt-2026-june/")
        )
        self.assertFalse(longato["include"]("https://www.longato.ch/blog/"))

        documented = dict(skillsllm.doc_sources())
        self.assertEqual(documented["OtterlyAI Blog"], "https://otterly.ai/blog/")
        self.assertEqual(documented["Flavio Longato"], "https://www.longato.ch/blog/")

    def test_graphify_native_feeds_are_registered(self):
        """Graphify blog and changelog should use their native upstream feeds."""
        feeds = {source[0]: source[1] for source in skillsllm.NATIVE_FEEDS}
        self.assertEqual(feeds["Graphify Blog"], "https://graphify.com/feed.xml")
        self.assertEqual(
            feeds["Graphify Changelog"],
            "https://github.com/Graphify-Labs/graphify/releases.atom",
        )

    def test_upstash_and_lobehub_native_feeds_are_registered(self):
        """Use Upstash RSS and LobeHub's locale-neutral feed endpoints."""
        feeds = {source[0]: source[1] for source in skillsllm.NATIVE_FEEDS}
        self.assertEqual(feeds["Upstash Blog"], "https://upstash.com/blog/feed.xml")
        self.assertEqual(feeds["LobeHub Blog"], "https://lobehub.com/blog/feed")
        self.assertEqual(
            feeds["LobeHub Changelog"], "https://lobehub.com/changelog/feed"
        )
        saas_urls = {source[1] for source in saas.NATIVE_FEEDS}
        self.assertNotIn("https://upstash.com/blog/feed.xml", saas_urls)
        self.assertIn("https://upstash.com/docs/workflow/changelog/rss.xml", saas_urls)
        kept = saas._active_cached_entries(
            [
                {"source": "Upstash Blog", "link": "https://upstash.com/blog/old"},
                {"source": "Cursor Changelog", "link": "https://cursor.com/changelog/x"},
            ]
        )
        self.assertEqual([entry["source"] for entry in kept], ["Cursor Changelog"])

    def test_legacy_lobehub_locale_cache_rows_are_retired(self):
        entries = [
            {"link": 123, "source": "Broken"},
            {"link": None, "source": "Broken"},
            {"source": "Broken"},
            {"link": "https://lobehub.com/pl/blog/old-post", "source": "LobeHub Blog"},
            {
                "link": "https://lobehub.com/pl/changelog/versions/v1#1.142.0",
                "source": "LobeHub Changelog",
            },
            {"link": "https://lobehub.com/blog/current-post", "source": "LobeHub Blog"},
            {"link": "https://example.com/pl/blog/keep", "source": "Other"},
        ]
        kept = skillsllm._active_cached_entries(entries)
        self.assertEqual(
            [entry["link"] for entry in kept],
            [
                "https://lobehub.com/blog/current-post",
                "https://example.com/pl/blog/keep",
            ],
        )

    def test_mcpso_surfaces_are_documented(self):
        """MCP.so's directory feed and editorial blog should both be visible."""
        sources = dict(skillsllm.doc_sources())
        self.assertEqual(sources["MCP.so Feed"], "https://mcp.so/feed")
        self.assertEqual(sources["MCP.so Blog"], "https://mcp.so/blog")
        self.assertEqual(skillsllm.PER_SOURCE_CAP["MCP.so Feed"], 10)

    def test_mcpso_feed_parser_uses_card_timestamp(self):
        html = """
        <a href="/servers/demo">
          <img src="/logo.png">
          <h3>Demo MCP</h3>
          <p class="line-clamp-2">Useful MCP server.</p>
          <span title="08/30/2026, 08:34 PM">Submitted recently</span>
        </a>
        """
        entries = skillsllm.parse_mcpso_feed(
            html, now=datetime(2026, 8, 30, 21, 0, tzinfo=skillsllm.pytz.UTC)
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["link"], "https://mcp.so/servers/demo")
        self.assertEqual(entries[0]["title"], "Demo MCP")
        self.assertEqual(entries[0]["description"], "Useful MCP server.")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-08-30T20:34:00+00:00")
        self.assertEqual(entries[0]["image"], "https://mcp.so/logo.png")

    def test_mcpso_feed_clamps_source_timestamps_from_the_future(self):
        """MCP.so currently exposes future createdAt values; do not promote them."""
        html = """
        <a href="/servers/future">
          <h3>Future MCP</h3>
          <span title="08/30/2026, 08:34 PM">Submitted in 5 hours</span>
        </a>
        """
        now = datetime(2026, 8, 30, 15, 0, tzinfo=skillsllm.pytz.UTC)
        entries = skillsllm.parse_mcpso_feed(html, now=now)
        self.assertEqual(entries[0]["date"], now)

    def test_mcpso_blog_parser_uses_visible_date(self):
        html = """
        <a href="/blog/graph-engineering">
          <h3>Graph Engineering</h3>
          <p class="line-clamp-3">A guide to agent graphs.</p>
          <span>Jul 21, 2026</span>
        </a>
        """
        entries = skillsllm.parse_mcpso_blog(html)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["link"], "https://mcp.so/blog/graph-engineering")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-07-21T00:00:00+00:00")

    def test_mcpso_blog_clamps_dates_from_the_future(self):
        html = """
        <a href="/blog/future-post">
          <h3>Future post</h3>
          <span>Sep 2, 2026</span>
        </a>
        """
        now = datetime(2026, 8, 30, 15, 0, tzinfo=skillsllm.pytz.UTC)
        entries = skillsllm.parse_mcpso_blog(html, now=now)
        self.assertEqual(entries[0]["date"], now)

    def test_collect_mcpso_caps_directory_feed_immediately(self):
        cards = "".join(
            f'<a href="/servers/demo-{i}"><h3>Demo {i}</h3></a>'
            for i in range(12)
        )
        with patch.object(skillsllm, "fetch_url", return_value=cards):
            entries = skillsllm.collect_mcpso(set())
        directory = [e for e in entries if e["source"] == "MCP.so Feed"]
        self.assertEqual(len(directory), 10)

    def test_native_feed_cleanup_recovers_invalid_xml_control_character(self):
        """LobeHub's current RFC 106 control byte should not poison its RSS."""
        raw = """<?xml version="1.0"?><rss version="2.0"><channel>
        <title>LobeHub Blog</title><link>https://lobehub.com/blog</link>
        <item><title>[RFC] 106 - \x08Desktop config</title>
        <link>https://lobehub.com/blog/rfc-106</link></item>
        </channel></rss>"""
        with (
            patch.object(
                skillsllm,
                "NATIVE_FEEDS",
                [("LobeHub Blog", "https://lobehub.com/blog/feed", "lobehub-blog", 30)],
            ),
            patch.object(skillsllm, "fetch_url", return_value=raw),
        ):
            entries = skillsllm.collect_native_feeds()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "[RFC] 106 - Desktop config")

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
