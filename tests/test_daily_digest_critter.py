import json
import random
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import daily_digest  # noqa: E402


# The date seeds the species, so both are pinned: 30.07 draws a dog, 31.07 a cat.
FIXED_NOW = datetime(2026, 7, 30, 12, 0, tzinfo=pytz.UTC)
FIXED_DAY = "2026-07-30"
CAT_DAY_NOW = datetime(2026, 7, 31, 12, 0, tzinfo=pytz.UTC)

# Every wired-up source, keyed by URL, so a test can answer whichever pair the
# day's seed happens to reach for without pinning the species.
ALL_RESPONSES = {
    "https://catfact.ninja/fact": {"fact": "Cats sleep a lot."},
    "https://meowfacts.herokuapp.com/": {"data": ["Cats have whiskers."]},
    "https://dogapi.dog/api/v2/facts": {
        "data": [{"attributes": {"body": "Dogs dream."}}]
    },
    "https://api.thecatapi.com/v1/images/search": [{"url": "https://cdn.example/cat.jpg"}],
    "https://cataas.com/cat?json=true": {"url": "https://cataas.com/cat/abc"},
    "https://random.dog/woof.json?filter=mp4,webm,mov": {
        "url": "https://random.dog/dog.jpg"
    },
}

EXPECTED_FACTS = {"Cats sleep a lot.", "Cats have whiskers.", "Dogs dream."}
EXPECTED_PICTURES = {
    "https://cdn.example/cat.jpg",
    "https://cataas.com/cat/abc",
    "https://random.dog/dog.jpg",
}


def _serve(responses, seen_headers=None):
    """fetch_json stand-in: answers from *responses*, None for anything else.

    Records the headers it was handed when *seen_headers* is given, which is how
    the anycrap tests check that the key travels in an Authorization header.
    """

    def fetch_json(url, retries=3, backoff=2.0, headers=None):
        if seen_headers is not None:
            seen_headers[url] = headers
        return responses.get(url)

    return fetch_json


class CritterOfTheDayTests(unittest.TestCase):
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_builds_one_entry_with_a_fact_and_a_picture(self, _mock_today):
        with patch.object(daily_digest, "fetch_json", side_effect=_serve(ALL_RESPONSES)):
            [entry] = daily_digest.adapt_critter()

        self.assertEqual(entry["guid"], f"critter:{FIXED_DAY}")
        self.assertEqual(entry["category"], "critter")
        self.assertIn(entry["title"], {"Cat Fact of the Day", "Dog Fact of the Day"})
        self.assertIn(entry["image"], EXPECTED_PICTURES)
        # The picture lookup already happened, so the image backfill must not
        # go asking a fact API's landing page for an og:image.
        self.assertTrue(entry["image_checked"])
        self.assertTrue(
            any(entry["description"].startswith(fact) for fact in EXPECTED_FACTS),
            entry["description"],
        )
        self.assertIn("Picture:", entry["description"])

    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_same_day_reruns_pick_the_same_species(self, _mock_today):
        with patch.object(daily_digest, "fetch_json", side_effect=_serve(ALL_RESPONSES)):
            [first] = daily_digest.adapt_critter()
            [second] = daily_digest.adapt_critter()

        self.assertEqual(first["title"], second["title"])
        self.assertEqual(first["source"], second["source"])

    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_a_missing_picture_still_yields_an_entry(self, _mock_today):
        fact_urls = {
            url
            for sources in daily_digest.CRITTER_FACT_SOURCES.values()
            for _, url, _, _ in sources
        }
        facts_only = {
            url: payload for url, payload in ALL_RESPONSES.items() if url in fact_urls
        }

        with patch.object(daily_digest, "fetch_json", side_effect=_serve(facts_only)):
            [entry] = daily_digest.adapt_critter()

        self.assertIsNone(entry["image"])
        self.assertTrue(entry["image_checked"])
        self.assertNotIn("Picture:", entry["description"])

    @patch.object(daily_digest, "_today_utc", return_value=CAT_DAY_NOW)
    def test_a_site_relative_picture_is_resolved_against_its_host(self, _mock_today):
        # Cataas has historically answered with "/cat/<id>"; published raw, that
        # renders as a broken image everywhere.
        responses = dict(ALL_RESPONSES)
        responses["https://cataas.com/cat?json=true"] = {"url": "/cat/abc"}
        responses.pop("https://api.thecatapi.com/v1/images/search")

        with patch.object(daily_digest, "fetch_json", side_effect=_serve(responses)):
            [entry] = daily_digest.adapt_critter()

        self.assertEqual(entry["image"], "https://cataas.com/cat/abc")

    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_no_fact_anywhere_yields_no_entry(self, _mock_today):
        with patch.object(daily_digest, "fetch_json", side_effect=_serve({})):
            self.assertEqual(daily_digest.adapt_critter(), [])

    def test_a_dead_source_hands_over_to_the_next_one(self):
        sources = (
            ("Dead", "https://dead.example/fact", "https://dead.example/",
             lambda data: data["fact"]),
            ("Alive", "https://alive.example/fact", "https://alive.example/",
             lambda data: data["fact"]),
        )
        responses = {"https://alive.example/fact": {"fact": "Still here."}}

        with patch.object(daily_digest, "fetch_json", side_effect=_serve(responses)):
            value, name, home, _ = daily_digest._pick_from_sources(
                sources, random.Random(0), what="fact"
            )

        self.assertEqual((value, name, home), ("Still here.", "Alive", "https://alive.example/"))

    def test_a_moved_field_hands_over_instead_of_raising(self):
        sources = (
            ("Moved", "https://moved.example/fact", "https://moved.example/",
             lambda data: data["fact"]),
            ("Alive", "https://alive.example/fact", "https://alive.example/",
             lambda data: data["fact"]),
        )
        responses = {
            "https://moved.example/fact": {"renamed_field": "Not where it was."},
            "https://alive.example/fact": {"fact": "Still here."},
        }

        with patch.object(daily_digest, "fetch_json", side_effect=_serve(responses)):
            value, name, _, _ = daily_digest._pick_from_sources(
                sources, random.Random(0), what="fact"
            )

        self.assertEqual((value, name), ("Still here.", "Alive"))

    def test_a_blank_answer_hands_over_instead_of_being_published(self):
        sources = (
            ("Blank", "https://blank.example/fact", "https://blank.example/",
             lambda data: data["fact"]),
            ("Alive", "https://alive.example/fact", "https://alive.example/",
             lambda data: data["fact"]),
        )
        responses = {
            "https://blank.example/fact": {"fact": "  \n "},
            "https://alive.example/fact": {"fact": "Still here."},
        }

        with patch.object(daily_digest, "fetch_json", side_effect=_serve(responses)):
            value, name, _, _ = daily_digest._pick_from_sources(
                sources, random.Random(0), what="fact"
            )

        self.assertEqual((value, name), ("Still here.", "Alive"))

    @patch.object(daily_digest, "adapt_anycrap")
    @patch.object(daily_digest, "adapt_critter")
    @patch.object(daily_digest, "adapt_holidays", return_value=[])
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_collect_entries_skips_the_fetch_once_the_day_is_cached(
        self, _mock_today, _mock_holidays, mock_critter, mock_anycrap
    ):
        cached = {f"critter:{FIXED_DAY}", f"anycrap:{FIXED_DAY}"}
        with patch.object(daily_digest, "_cached_guids", return_value=cached), \
             patch.object(daily_digest, "fetch_json", side_effect=_serve({})):
            daily_digest.collect_entries()

        mock_critter.assert_not_called()
        mock_anycrap.assert_not_called()

    @patch.object(daily_digest, "adapt_anycrap", return_value=[])
    @patch.object(daily_digest, "adapt_critter", return_value=[])
    @patch.object(daily_digest, "adapt_holidays", return_value=[])
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_a_full_rebuild_fetches_even_with_a_cached_day(
        self, _mock_today, _mock_holidays, mock_critter, mock_anycrap
    ):
        with patch.object(daily_digest, "_cached_guids") as cached_guids, \
             patch.object(daily_digest, "fetch_json", side_effect=_serve({})):
            daily_digest.collect_entries(full=True)

        mock_critter.assert_called_once()
        mock_anycrap.assert_called_once()
        # A full rebuild must not even open the cache it is about to ignore.
        cached_guids.assert_not_called()

    @patch.object(daily_digest, "adapt_anycrap", return_value=[])
    @patch.object(daily_digest, "adapt_critter", return_value=[])
    @patch.object(daily_digest, "adapt_holidays", return_value=[])
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_the_cache_is_read_once_for_both_daily_sources(
        self, _mock_today, _mock_holidays, _mock_critter, _mock_anycrap
    ):
        with patch.object(daily_digest, "_cached_guids", return_value=set()) as cached_guids, \
             patch.object(daily_digest, "fetch_json", side_effect=_serve({})):
            daily_digest.collect_entries()

        cached_guids.assert_called_once()


ANYCRAP_PRODUCT = {
    "data": [{
        "slug": "thought-cancelling-headphones",
        "name": "Thought-Cancelling Headphones",
        "description": "Headphones that don't just block sound.",
        "image": "https://cdn.example/headphones.jpg",
        "categories": ["gadgets", "anti-productivity"],
    }]
}


class AnycrapProductOfTheDayTests(unittest.TestCase):
    @patch.dict("os.environ", {"ANYCRAP_API_KEY": "test-key"}, clear=False)
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_builds_a_daily_entry_and_sends_the_key_as_a_bearer(self, _mock_today):
        seen = {}
        responses = {daily_digest.ANYCRAP_RANDOM_URL: ANYCRAP_PRODUCT}

        with patch.object(daily_digest, "fetch_json", side_effect=_serve(responses, seen)):
            [entry] = daily_digest.adapt_anycrap()

        self.assertEqual(entry["guid"], f"anycrap:{FIXED_DAY}")
        self.assertEqual(entry["title"], "Product of the Day — Thought-Cancelling Headphones")
        self.assertEqual(
            entry["link"], "https://anycrap.shop/product/thought-cancelling-headphones"
        )
        self.assertEqual(entry["image"], "https://cdn.example/headphones.jpg")
        self.assertIn("gadgets, anti-productivity", entry["description"])
        # The key belongs in a header, never in the URL, which is the only thing
        # fetch_json logs.
        self.assertEqual(
            seen[daily_digest.ANYCRAP_RANDOM_URL]["Authorization"], "Bearer test-key"
        )
        self.assertNotIn("test-key", daily_digest.ANYCRAP_RANDOM_URL)

    @patch.dict("os.environ", {"ANYCRAP_API_KEY": ""}, clear=False)
    def test_without_a_key_the_source_sits_out_instead_of_failing(self):
        with patch.object(daily_digest, "fetch_json") as fetch_json:
            self.assertEqual(daily_digest.adapt_anycrap(), [])

        fetch_json.assert_not_called()

    @patch.dict("os.environ", {"ANYCRAP_API_KEY": "test-key"}, clear=False)
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_a_relative_product_image_is_resolved_and_a_missing_one_stays_open(
        self, _mock_today
    ):
        relative = json.loads(json.dumps(ANYCRAP_PRODUCT))
        relative["data"][0]["image"] = "/img/headphones.jpg"
        missing = json.loads(json.dumps(ANYCRAP_PRODUCT))
        del missing["data"][0]["image"]

        with patch.object(
            daily_digest, "fetch_json",
            side_effect=_serve({daily_digest.ANYCRAP_RANDOM_URL: relative}),
        ):
            [entry] = daily_digest.adapt_anycrap()
        self.assertEqual(entry["image"], "https://anycrap.shop/img/headphones.jpg")

        with patch.object(
            daily_digest, "fetch_json",
            side_effect=_serve({daily_digest.ANYCRAP_RANDOM_URL: missing}),
        ):
            [entry] = daily_digest.adapt_anycrap()
        self.assertIsNone(entry["image"])
        # The link is a real product page, so leave the backfill free to try it.
        self.assertFalse(entry["image_checked"])

    @patch.dict("os.environ", {"ANYCRAP_API_KEY": "test-key"}, clear=False)
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_an_odd_blurb_or_slug_costs_neither_the_entry_nor_the_link(self, _mock_today):
        payload = json.loads(json.dumps(ANYCRAP_PRODUCT))
        payload["data"][0]["description"] = {"text": "an object, not a string"}
        payload["data"][0]["slug"] = "a slug/with spaces"

        with patch.object(
            daily_digest, "fetch_json",
            side_effect=_serve({daily_digest.ANYCRAP_RANDOM_URL: payload}),
        ):
            [entry] = daily_digest.adapt_anycrap()

        self.assertEqual(
            entry["link"], "https://anycrap.shop/product/a%20slug%2Fwith%20spaces"
        )
        self.assertTrue(entry["description"])

    @patch.dict("os.environ", {"ANYCRAP_API_KEY": "test-key"}, clear=False)
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_an_unusable_payload_yields_no_entry(self, _mock_today):
        responses = {daily_digest.ANYCRAP_RANDOM_URL: {"data": []}}

        with patch.object(daily_digest, "fetch_json", side_effect=_serve(responses)):
            self.assertEqual(daily_digest.adapt_anycrap(), [])


class DigestImageRenderingTests(unittest.TestCase):
    def test_an_entry_image_reaches_the_atom_output(self):
        entries = [{
            "guid": "critter:2026-07-30",
            "link": "https://catfact.ninja/",
            "title": "Cat Fact of the Day",
            "description": "Cats sleep a lot.",
            "date": FIXED_NOW,
            "source": "Cat Fact Ninja",
            "category": "critter",
            "image": "https://cdn.example/cat.jpg",
        }]

        xml = daily_digest.generate_atom_feed(entries).atom_str(pretty=True).decode("utf-8")

        self.assertIn("https://cdn.example/cat.jpg", xml)
        self.assertIn("media:thumbnail", xml)


if __name__ == "__main__":
    unittest.main()
