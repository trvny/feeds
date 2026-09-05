"""docs/sources.md is meant to be an exact list of what feeds each feed.

Every test here pins a shape that was silently dropping sources: the document
claimed geopolitics had two, google one, olx one. Nothing here touches the
network or the real generators - the collector is fed hand-built module stubs.
"""

import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import docs_sources as ds  # noqa: E402


def stub(name="stub_generator", **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def is_host(url: str, hostname: str) -> bool:
    parsed = (urlsplit(url).hostname or "").lower()
    hostname = hostname.lower()
    return parsed == hostname or parsed.endswith(f".{hostname}")


class PairExtractionTests(unittest.TestCase):
    def test_reads_label_url_cap_tuples(self):
        value = [("RUSI Commentary", "https://www.rusi.org/rss/latest-commentary.xml", 40)]
        self.assertEqual(
            ds._pairs_from_value(value),
            [("RUSI Commentary", "https://www.rusi.org/rss/latest-commentary.xml")],
        )

    def test_finds_the_url_when_it_is_not_the_second_element(self):
        # olx_group declares (label, category, url); reading position 1 blindly
        # dropped all five of its feeds.
        value = [("OLX Blog", "olx", "https://blog.olx.pl/feed/")]
        self.assertEqual(
            ds._pairs_from_value(value), [("OLX Blog", "https://blog.olx.pl/feed/")]
        )

    def test_reads_dataclass_sources(self):
        # google declares Source(key, label, url, ...) instances, not tuples.
        @dataclass(frozen=True)
        class Source:
            key: str
            label: str
            url: str

        self.assertEqual(
            ds._pairs_from_value([Source("firebase", "Firebase", "https://firebase.blog/rss.xml")]),
            [("Firebase", "https://firebase.blog/rss.xml")],
        )

    def test_falls_back_to_the_host_when_a_source_has_no_label(self):
        self.assertEqual(
            ds._pairs_from_value([("", "https://example.com/feed")]),
            [("example.com", "https://example.com/feed")],
        )


class UrlConstantTests(unittest.TestCase):
    def test_collects_scraper_constants(self):
        module = stub(ISW_URL="https://understandingwar.org/research/")
        self.assertEqual(
            ds._url_constant_pairs(module), [("ISW", "https://understandingwar.org/research/")]
        )

    def test_a_template_is_reduced_to_something_clickable(self):
        # euronews once shipped a literal "{level}" into the document. Cutting
        # at the placeholder instead leaves half a URL, which mostly 404s - and
        # tools/check_sources.py then reports a working source as dead.
        module = stub(CARNEGIE_API="https://carnegieendowment.org/api/{collection}?limit=20")
        self.assertEqual(
            ds._url_constant_pairs(module), [("Carnegie", "https://carnegieendowment.org")]
        )

    def test_skips_icons_and_other_non_sources(self):
        module = stub(
            USAGOV_ICON="https://www.usa.gov/themes/custom/img/Favicon.png",
            USER_AGENT_URL="https://example.com/bot",
        )
        self.assertEqual(ds._url_constant_pairs(module), [])

    def test_labels_read_like_names_not_constants(self):
        module = stub(
            MESSAGE_CENTER_URL="https://learn.microsoft.com/message-center",
            GSA_BLOG="https://www.gsa.gov/blog",
            BLOG_URL="https://blog.google/",
        )
        self.assertEqual(
            [label for label, _ in ds._url_constant_pairs(module)],
            ["Blog", "GSA blog", "Message center"],
        )


class ModuleCompositionTests(unittest.TestCase):
    def test_a_bare_base_url_is_not_listed_as_its_own_source(self):
        module = stub(
            MINIMAX_BASE_URL="https://www.minimax.io",
            MINIMAX_NEWS_URL="https://www.minimax.io/news",
        )
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__, None)
        self.assertEqual(
            [url for _, url in ds.sources_by_import(f"{module.__name__}.py")],
            ["https://www.minimax.io/news"],
        )

    def test_doc_sources_hook_is_merged_in(self):
        # For generators that build URLs in code (youtubs, 4chan), which no
        # amount of reading constants could recover.
        module = stub(
            SOURCES=[("Declared", "https://example.com/feed")],
            doc_sources=lambda: [("/g/ Technology", "https://boards.4chan.org/g/")],
        )
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__, None)
        self.assertEqual(
            sorted(url for _, url in ds.sources_by_import(f"{module.__name__}.py")),
            ["https://boards.4chan.org/g/", "https://example.com/feed"],
        )

    def test_a_broken_hook_does_not_sink_the_document(self):
        def explode():
            raise RuntimeError("boom")

        module = stub(SOURCES=[("Declared", "https://example.com/feed")], doc_sources=explode)
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__, None)
        self.assertEqual(
            [url for _, url in ds.sources_by_import(f"{module.__name__}.py")],
            ["https://example.com/feed"],
        )


class RealGeneratorTests(unittest.TestCase):
    """The three the document actually got wrong, checked against the real code."""

    def counts(self, script):
        return len(ds.sources_by_import(script))

    def test_geopolitics_lists_its_scrapers_not_just_its_rss(self):
        urls = [url for _, url in ds.sources_by_import("geopolitics.py")]
        self.assertIn("https://understandingwar.org/research/", urls)
        self.assertIn("https://www.csis.org/analysis", urls)

    def test_google_lists_more_than_its_own_blog(self):
        self.assertGreater(self.counts("google.py"), 15)

    def test_olx_lists_all_five_feeds(self):
        self.assertEqual(self.counts("olx_group.py"), 5)

    def test_a_composed_generator_inherits_what_it_scrapes(self):
        # aibridge imports groq's and perplexity's scrapers as functions,
        # not as modules.
        urls = [url for _, url in ds.sources_by_import("aibridge.py")]
        self.assertTrue(any(is_host(url, "groq.com") for url in urls))
        self.assertTrue(any(is_host(url, "perplexity.ai") for url in urls))

    def test_anthropic_lists_sources_from_its_private_base(self):
        sources = ds.sources_by_import("anthropic.py")
        self.assertEqual(sources[0], ("Anthropic Newsroom", "https://www.anthropic.com/news"))
        by_label = dict(sources)
        self.assertEqual(by_label["Anthropic Red"], "https://red.anthropic.com/")
        self.assertEqual(by_label["Anthropic Alignment Science"], "https://alignment.anthropic.com/")
        self.assertEqual(
            by_label["Anthropic Interpretability"],
            "https://transformer-circuits.pub/feed.xml",
        )

    def test_internal_transport_endpoints_do_not_leak_into_source_docs(self):
        openoffice = {url for _, url in ds.sources_by_import("openoffice.py")}
        tvp = {url for _, url in ds.sources_by_import("tvp.py")}
        open_meteo = {url for _, url in ds.sources_by_import("open_meteo.py")}

        self.assertFalse(
            any(
                is_host(url, "onlyoffice.com")
                and urlsplit(url).path.startswith("/blog/api/")
                for url in openoffice
            )
        )
        self.assertFalse(
            any(
                is_host(url, "tvp.pl")
                and urlsplit(url).path.startswith("/api/")
                for url in tvp
            )
        )
        self.assertFalse(
            any(is_host(url, "satellite-api.open-meteo.com") for url in open_meteo)
        )
        self.assertIn(
            "https://open-meteo.com/en/docs/satellite-radiation-api",
            open_meteo,
        )

    def test_registered_source_urls_have_single_owner(self):
        """One upstream URL should feed one public aggregate, not several."""
        feeds = ds.load_yaml_feeds()
        owners = {}
        for feed_name, config in feeds.items():
            pairs, _ = ds.collect_sources(feed_name, config)
            for label, url in pairs:
                owners.setdefault(url, []).append((feed_name, label))

        duplicates = {
            url: rows for url, rows in owners.items() if len({feed for feed, _ in rows}) > 1
        }
        self.assertEqual({}, duplicates)


if __name__ == "__main__":
    unittest.main()
