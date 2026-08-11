import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from czworka import FETCH_BASE_URL, _canonical, discover_links  # noqa: E402


class CzworkaTests(unittest.TestCase):
    def test_canonical_keeps_existing_public_article_identity(self):
        self.assertEqual(
            _canonical(
                "https://czworka.online/10/216/Artykul/3718215,"
                "Zdjecia-do-drugiej-czesci"
            ),
            "https://www.polskieradio.pl/10/216/Artykul/3718215",
        )

    def test_discovery_routes_article_fetches_through_dedicated_host(self):
        html = (
            '<a href="/10/216/Artykul/3718215,example">Czwórka</a>'
            '<a href="/7/123/Artykul/9999999,other">Jedynka</a>'
        )

        self.assertEqual(
            discover_links(html),
            [f"{FETCH_BASE_URL}/10/216/Artykul/3718215,example"],
        )


if __name__ == "__main__":
    unittest.main()
