"""Round-robin slot allocation across a combined feed's sources.

Guards the fix for measured starvation in published feeds (11.08.2026): steam
published 7 of the 20 sources sitting in its cache, cheezburger 4 of 6 with two
at zero entries, and lemmy gave 128 of 250 slots to sh.itjust.works despite an
explicit per-source cap of 50 — because leftover slots were refilled from an
overflow pool ordered by recency alone, which the busiest source dominates.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from utils import allocate_fair_share  # noqa: E402


def entries(source, count, day, start=0):
    """`count` entries for one source on `day`, ascending by date."""
    return [
        {
            "date": f"2026-01-{day:02d}T00:{i:02d}:00+00:00",
            "source": source,
            "n": f"{source}{i}",
        }
        for i in range(start, start + count)
    ]


def ascending(*groups):
    merged = [e for group in groups for e in group]
    merged.sort(key=lambda e: e["date"])
    return merged


def counts(selected):
    tally = {}
    for e in selected:
        tally[e["source"]] = tally.get(e["source"], 0) + 1
    return tally


class FairShareTests(unittest.TestCase):
    def test_every_source_places_its_newest_before_anyone_places_a_second(self):
        # The core guarantee. Three sources, only two slots per source available,
        # so a recency slice would have returned the busy source's top 3 alone.
        busy = entries("busy", 20, day=3)
        mid = entries("mid", 5, day=2)
        rare = entries("rare", 1, day=1)
        selected = allocate_fair_share(ascending(busy, mid, rare), limit=3)
        self.assertEqual(counts(selected), {"busy": 1, "mid": 1, "rare": 1})

    def test_rare_source_keeps_its_latest_post_visible(self):
        # A source that publishes a few times a year must not be evicted by one
        # that publishes hourly — it holds its slot until it publishes again.
        hourly = entries("hourly", 500, day=9)
        yearly = entries("yearly", 1, day=1)
        selected = allocate_fair_share(ascending(hourly, yearly), limit=100)
        self.assertEqual(counts(selected).get("yearly"), 1)
        self.assertEqual(len(selected), 100)

    def test_slots_freed_by_a_quiet_source_spread_evenly(self):
        # The lemmy bug: Lemmy.world had 22 entries and Lemmy.org none, so 78 of
        # 250 slots went spare — and all 78 went to the single busiest source.
        busy_a = entries("a", 300, day=5)
        busy_b = entries("b", 300, day=5)
        quiet = entries("quiet", 4, day=1)
        selected = allocate_fair_share(ascending(busy_a, busy_b, quiet), limit=100)
        tally = counts(selected)
        self.assertEqual(tally["quiet"], 4)
        self.assertEqual(len(selected), 100)
        self.assertLessEqual(abs(tally["a"] - tally["b"]), 1, "spare slots went lopsided")

    def test_int_cap_does_not_shrink_the_feed(self):
        # An int cap is a first-pass target, not a wall: once every source has
        # hit it, remaining slots are refilled rather than left empty.
        selected = allocate_fair_share(
            ascending(entries("a", 200, day=5), entries("b", 200, day=5)),
            limit=100,
            per_source_cap=10,
        )
        self.assertEqual(len(selected), 100)
        tally = counts(selected)
        self.assertLessEqual(abs(tally["a"] - tally["b"]), 1)

    def test_mapping_cap_stays_a_hard_ceiling(self):
        # Naming a source explicitly is how this repo throttles a content farm,
        # so a mapping must hold through both passes even if the feed ends short.
        selected = allocate_fair_share(
            ascending(entries("farm", 500, day=5), entries("editorial", 20, day=4)),
            limit=100,
            per_source_cap={"farm": 5, "editorial": 40, "": 30},
        )
        tally = counts(selected)
        self.assertEqual(tally["farm"], 5)
        self.assertEqual(tally["editorial"], 20)
        self.assertEqual(len(selected), 25)

    def test_mapping_default_applies_to_unnamed_sources(self):
        selected = allocate_fair_share(
            ascending(entries("named", 100, day=5), entries("other", 100, day=5)),
            limit=100,
            per_source_cap={"named": 2, "": 3},
        )
        self.assertEqual(counts(selected), {"named": 2, "other": 3})

    def test_result_stays_ascending_by_date(self):
        selected = allocate_fair_share(
            ascending(entries("a", 40, day=4), entries("b", 40, day=2)), limit=20
        )
        dates = [e["date"] for e in selected]
        self.assertEqual(dates, sorted(dates))

    def test_rotation_follows_sorted_source_names_not_dict_order(self):
        # Rotation must not depend on the order sources happened to be scraped
        # in, or the same cache would yield a different feed between runs. With
        # 5 slots over 3 equal sources the two remainder slots go to the
        # alphabetically first two, every time.
        data = ascending(
            entries("z", 10, day=5), entries("a", 10, day=4), entries("m", 10, day=3)
        )
        selected = allocate_fair_share(data, limit=5)
        self.assertEqual(counts(selected), {"a": 2, "m": 2, "z": 1})
        self.assertEqual(
            [e["n"] for e in selected],
            [e["n"] for e in allocate_fair_share(data, limit=5)],
        )

    def test_noop_below_limit(self):
        data = ascending(entries("a", 3, day=1), entries("b", 2, day=2))
        self.assertEqual(len(allocate_fair_share(data, limit=50)), 5)

    def test_single_source_degrades_to_recency(self):
        selected = allocate_fair_share(entries("only", 20, day=1), limit=5)
        self.assertEqual([e["n"] for e in selected], [f"only{i}" for i in range(15, 20)])

    def test_unlabelled_entries_are_one_bucket(self):
        # 14 feeds do not set `source` at all; they must keep working unchanged.
        data = [{"date": f"2026-01-01T00:{i:02d}:00+00:00", "n": i} for i in range(20)]
        selected = allocate_fair_share(data, limit=5)
        self.assertEqual([e["n"] for e in selected], [15, 16, 17, 18, 19])

    def test_measured_lemmy_shape_is_no_longer_lopsided(self):
        # Cache proportions as committed on 11.08.2026, with the cap lemmy sets.
        selected = allocate_fair_share(
            ascending(
                entries("sh.itjust.works", 1463, day=9),
                entries("Lemmy.ml", 360, day=8),
                entries("Szmer", 155, day=7),
                entries("Lemmy.world", 22, day=6),
            ),
            limit=250,
            per_source_cap=50,
        )
        tally = counts(selected)
        self.assertEqual(len(selected), 250)
        self.assertEqual(tally["Lemmy.world"], 22)
        self.assertLess(max(tally.values()) / 250, 0.35, "one source still dominates")


if __name__ == "__main__":
    unittest.main()
