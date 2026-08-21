import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import anthropic  # noqa: E402
import github  # noqa: E402
import google  # noqa: E402
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

    def test_skillsllm_includes_mem0_blog_and_research(self):
        sources = {source["label"]: source for source in skillsllm.SOURCES}
        self.assertIn("Mem0 Blog", sources)
        self.assertIn("Mem0 Research", sources)
        research = sources["Mem0 Research"]
        self.assertEqual(research["sitemap"], "https://mem0.ai/sitemap.xml")
        self.assertTrue(research["include"]("https://mem0.ai/research"))
        self.assertFalse(research["include"]("https://mem0.ai/blog/example"))

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


if __name__ == "__main__":
    unittest.main()
