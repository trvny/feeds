import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import thirteen37x

SAMPLE = """
<div class="box-info trending"><h1>Movies Torrents download list</h1></div>
<div class="featured-list"><table class="table-list"><tbody>
<tr>
  <td class="coll-1 name"><a href="/sub/42/0/">HD</a><a href="/torrent/123/example-release/">Example.Release.2026</a></td>
  <td class="coll-2 seeds">321</td><td class="coll-3 leeches">45</td>
  <td class="coll-date">2:30pm</td>
  <td class="coll-4 size mob-uploader">1.8 GB<span class="seeds">321</span></td>
  <td class="coll-5 uploader"><a href="/user/example/">example</a></td>
</tr>
</tbody></table></div>
"""


class Thirteen37xTests(unittest.TestCase):
    def test_parser_extracts_trending_metadata(self):
        entry = thirteen37x.parse_trending(SAMPLE)[0]

        self.assertEqual(entry["title"], "Example.Release.2026")
        self.assertEqual(entry["link"], "https://1337x.to/torrent/123/example-release")
        self.assertEqual(entry["source"], "1337x / Movies")
        self.assertIsNone(entry["date"])
        self.assertIn("Seeds: 321", entry["description"])
        self.assertIn("Leeches: 45", entry["description"])
        self.assertIn("Size: 1.8 GB", entry["description"])
        self.assertIn("Uploader: example", entry["description"])

    def test_parser_skips_known_links(self):
        known = {"https://1337x.to/torrent/123/example-release/"}
        self.assertEqual(thirteen37x.parse_trending(SAMPLE, known), [])

    def test_scraper_falls_back_between_fetch_urls(self):
        with patch.object(
            thirteen37x,
            "get_html",
            side_effect=[None, SAMPLE],
        ) as fetch:
            entries = thirteen37x.scrape_1337x(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args_list[0].args[0], thirteen37x.FETCH_URLS[0])
        self.assertEqual(fetch.call_args_list[1].args[0], thirteen37x.FETCH_URLS[1])


if __name__ == "__main__":
    unittest.main()
