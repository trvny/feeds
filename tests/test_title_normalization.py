"""Regression coverage for Unicode-safe title deduplication."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "feed_generators"))

from utils import dedupe_entries, normalize_title  # noqa: E402


class TitleNormalizationTests(unittest.TestCase):
    def test_preserves_unicode_letters_and_digits(self):
        cases = {
            "ŻÓŁĆ — Łódź 2026!": "żółć łódź 2026",
            "ПРИВЕТ, мир!": "привет мир",
            "中文：更新 2026": "中文 更新 2026",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(normalize_title(title), expected)

    def test_distinct_unicode_titles_do_not_collapse_to_same_ascii_fragment(self):
        entries = [
            {"link": "https://example.com/lodz", "title": "Łódź A", "date": None},
            {"link": "https://example.com/zadz", "title": "Żądź A", "date": None},
        ]
        self.assertEqual(len(dedupe_entries(entries)), 2)

    def test_unicode_case_and_punctuation_variants_still_dedupe(self):
        entries = [
            {"link": "https://example.com/one", "title": "ŻÓŁĆ — test", "date": None},
            {"link": "https://example.com/two", "title": "żółć test", "date": None},
        ]
        self.assertEqual(len(dedupe_entries(entries)), 1)

    def test_canonical_equivalents_normalize_identically(self):
        self.assertEqual(normalize_title("Ku\u0308hn"), normalize_title("Kühn"))

    def test_combining_marks_keep_distinct_indic_titles_distinct(self):
        entries = [
            {"link": "https://example.com/ki", "title": "किताब", "date": None},
            {"link": "https://example.com/ku", "title": "कुताब", "date": None},
        ]
        self.assertEqual(len(dedupe_entries(entries)), 2)

    def test_canonical_mark_order_normalizes_before_casefold(self):
        first = "α\u0301\u0345"
        second = "α\u0345\u0301"
        self.assertEqual(normalize_title(first), normalize_title(second))

    def test_ascii_behavior_is_unchanged(self):
        self.assertEqual(normalize_title("Hello, WORLD! 2026"), "hello world 2026")


if __name__ == "__main__":
    unittest.main()
