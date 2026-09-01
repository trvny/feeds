import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import anthropic  # noqa: E402
import claude  # noqa: E402
import github  # noqa: E402
import google  # noqa: E402
import google_ai_studio  # noqa: E402
import microsoft  # noqa: E402
import python  # noqa: E402
import rutracker  # noqa: E402
import skillsllm  # noqa: E402


class RequestedFeedSourcesTests(unittest.TestCase):
    def test_anthropic_research_is_aggregated(self):
        urls = {source[1] for source in anthropic.SOURCES}
        self.assertIn("https://www.anthropic.com/research", urls)

    def test_skillsllm_native_feeds_include_requested_sources(self):
        urls = {source[1] for source in skillsllm.NATIVE_FEEDS}
        self.assertIn("https://huggingface.co/blog/feed.xml", urls)
        self.assertIn("https://www.mindstudio.ai/rss.xml", urls)
        self.assertIn("https://www.mintlify.com/docs/changelog/rss.xml", urls)
        self.assertIn("https://www.mintlify.com/feed.xml", urls)

    def test_claude_includes_platform_release_notes_feed(self):
        urls = {source[1] for source in claude.RSS_SOURCES}
        self.assertIn(
            "https://platform.claude.com/docs/en/release-notes/feed.xml", urls
        )

    def test_claude_migrates_legacy_platform_rows_after_rss_success(self):
        legacy_link = (
            "https://platform.claude.com/docs/en/release-notes/"
            "overview#example"
        )
        legacy = {
            "link": legacy_link,
            "source": claude.LEGACY_PLATFORM_RELEASE_SOURCE,
        }
        other = {
            "link": "https://claude.com/blog/example",
            "source": "Claude Blog",
        }
        native = {"link": legacy_link, "source": "Claude Platform"}

        known = claude._known_links_for_refresh([legacy, other])
        self.assertNotIn(legacy_link, known)
        self.assertIn(other["link"], known)
        self.assertEqual(
            claude._cache_for_merge([legacy, other], []),
            [legacy, other],
        )
        self.assertEqual(
            claude._cache_for_merge([legacy, other], [native]),
            [other],
        )

    def test_microsoft_includes_requested_sources(self):
        urls = {source[1] for source in microsoft.SOURCES}
        self.assertIn("https://opensource.microsoft.com/blog/feed/", urls)
        self.assertIn("https://microsoft.github.io/mcscatblog/feed.xml", urls)

    def test_skillsllm_includes_mem0_blog_and_research(self):
        sources = {source["label"]: source for source in skillsllm.SOURCES}
        self.assertIn("Mem0 Blog", sources)
        self.assertIn("Mem0 Research", sources)
        research = sources["Mem0 Research"]
        self.assertEqual(research["sitemap"], "https://mem0.ai/sitemap.xml")
        self.assertTrue(research["include"]("https://mem0.ai/research"))
        self.assertFalse(research["include"]("https://mem0.ai/blog/example"))

    def test_skillsllm_includes_desktop_commander_blog(self):
        sources = {source["label"]: source for source in skillsllm.SOURCES}
        desktop_commander = sources["Desktop Commander"]
        self.assertEqual(
            desktop_commander["sitemap"],
            "https://desktopcommander.app/sitemap.xml",
        )
        self.assertTrue(
            desktop_commander["include"](
                "https://desktopcommander.app/blog/ai-code-review-with-desktop-commander-a-practical-guide/"
            )
        )
        self.assertFalse(
            desktop_commander["include"](
                "https://desktopcommander.app/blog/category/mcp/"
            )
        )
        self.assertFalse(
            desktop_commander["include"]("https://desktopcommander.app/blog/about/")
        )
        self.assertFalse(
            desktop_commander["include"]("https://desktopcommander.app/blog/contact/")
        )

    def test_rutracker_contains_all_requested_atom_feeds(self):
        urls = {source[1] for source in rutracker.SOURCES}
        self.assertEqual(
            urls,
            {
                "https://feed.rutracker.cc/atom/f/0.atom",
                "https://feed.rutracker.cc/atom/f/1960.atom",
                "https://feed.rutracker.cc/atom/f/1880.atom",
                "https://feed.rutracker.cc/atom/f/1893.atom",
                "https://feed.rutracker.cc/atom/f/1397.atom",
                "https://feed.rutracker.cc/atom/f/1857.atom",
                "https://feed.rutracker.cc/atom/f/784.atom",
                "https://feed.rutracker.cc/atom/f/786.atom",
                "https://feed.rutracker.cc/atom/f/1631.atom",
                "https://feed.rutracker.cc/atom/f/2331.atom",
            },
        )

    def test_github_includes_beeware_news(self):
        self.assertIn(
            (github.BEEWARE_LABEL, github.BEEWARE_NEWS_URL),
            github.doc_sources(),
        )

    def test_python_includes_anaconda_feed(self):
        urls = {source[1] for source in python.SOURCES}
        self.assertIn("https://www.anaconda.com/feed", urls)

    def test_google_already_includes_firebase_feed(self):
        urls = {source.url for source in google.SOURCES}
        self.assertIn("https://firebase.blog/rss.xml", urls)

    def test_google_includes_antigravity_blog_and_changelog(self):
        self.assertEqual(google.ANTIGRAVITY_BLOG, "https://antigravity.google/blog")
        self.assertEqual(
            google.ANTIGRAVITY_CHANGELOG,
            "https://antigravity.google/changelog",
        )

    def test_google_parses_antigravity_changelog_release(self):
        html = """
        <article>
          <a href="/releases?tab=hub&amp;version=2.6.0">2.6.0</a>
          <time>August 7, 2026</time>
          <h3>Faster long conversations, more reliable hooks and subagents</h3>
          <p>Conversations with long histories now open faster.</p>
          <h4>Improvements (9)</h4>
          <ul><li>Improved the ask questions panel.</li></ul>
        </article>
        """
        entries = google._parse_antigravity_changelog(html)
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["title"],
            "Antigravity 2.6.0 — Faster long conversations, more reliable hooks and subagents",
        )
        self.assertEqual(entries[0]["date"].isoformat(), "2026-08-07T00:00:00+00:00")
        self.assertEqual(
            entries[0]["description"],
            "Conversations with long histories now open faster.",
        )
        self.assertEqual(entries[0]["source"], "Antigravity Changelog")

    def test_google_includes_ai_studio_release_notes(self):
        self.assertEqual(
            google.AI_STUDIO_CHANGELOG_URL,
            "https://aistudio.google.com/docs/changelog",
        )

    def test_google_parses_ai_studio_release_notes(self):
        html = """
        <main>
          <h2 id="august-20-2026">August 20, 2026</h2>
          <p>Added a new Build mode workflow.</p>
          <ul><li>Improved project export reliability.</li></ul>
          <h2 id="august-12-2026">August 12, 2026</h2>
          <p>Updated model controls in the Playground.</p>
        </main>
        """
        entries = google_ai_studio._parse_ai_studio_changelog(html)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Google AI Studio — 2026-08-20")
        self.assertEqual(
            entries[0]["description"],
            "Added a new Build mode workflow. Improved project export reliability.",
        )
        self.assertEqual(entries[0]["source"], "Google AI Studio")
        self.assertEqual(
            entries[0]["link"],
            "https://aistudio.google.com/docs/changelog#august-20-2026",
        )


if __name__ == "__main__":
    unittest.main()
