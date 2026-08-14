"""The picture in a feed entry is usually in its HTML, not in a media tag.

Measured 12.08.2026 across six upstream feeds: 0 of 150 items carried MRSS or
an enclosure, 103 carried an <img> in the description. Reading only the
structured fields is why 77% of published entries looked imageless.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from bs4 import BeautifulSoup  # noqa: E402

from utils import feed_item_image, feedparser_entry_image, html_image  # noqa: E402


class HtmlImageTests(unittest.TestCase):
    def test_takes_the_first_real_image(self):
        html = '<p>lead</p><img src="https://cdn.test/hero.jpg" width="800"><p>more</p>'
        self.assertEqual(html_image(html), "https://cdn.test/hero.jpg")

    def test_skips_tracking_beacons_and_avatars(self):
        html = (
            '<img src="https://feeds.feedburner.com/~ff/pixel.gif">'
            '<img src="https://gravatar.com/avatar/abc">'
            '<img src="https://cdn.test/real.jpg">'
        )
        self.assertEqual(html_image(html), "https://cdn.test/real.jpg")

    def test_skips_anything_declaring_a_tiny_size(self):
        # No article illustration is 1px; every spacer gif is.
        html = '<img src="https://cdn.test/a.gif" width="1" height="1">' '<img src="https://cdn.test/b.jpg">'
        self.assertEqual(html_image(html), "https://cdn.test/b.jpg")

    def test_skips_inline_data_uris(self):
        html = '<img src="data:image/png;base64,AAAA"><img src="https://cdn.test/c.jpg">'
        self.assertEqual(html_image(html), "https://cdn.test/c.jpg")

    def test_resolves_a_relative_src_against_the_entry(self):
        html = '<img src="/media/a.jpg">'
        self.assertEqual(
            html_image(html, "https://example.com/posts/one"), "https://example.com/media/a.jpg"
        )

    def test_a_relative_src_with_no_base_is_not_emitted(self):
        # A bare "/media/a.jpg" in a feed would render broken everywhere.
        self.assertIsNone(html_image('<img src="/media/a.jpg">'))

    def test_no_image_yields_nothing(self):
        self.assertIsNone(html_image("<p>just words</p>"))
        self.assertIsNone(html_image(""))


class FeedItemImageTests(unittest.TestCase):
    def item(self, xml):
        return BeautifulSoup(xml, "xml").find("item")

    def test_structured_media_still_wins_over_the_body(self):
        item = self.item(
            """<item>
                 <link>https://example.com/a</link>
                 <media:content xmlns:media="http://search.yahoo.com/mrss/"
                                url="https://cdn.test/declared.jpg" medium="image"/>
                 <description>&lt;img src="https://cdn.test/body.jpg"&gt;</description>
               </item>"""
        )
        self.assertEqual(feed_item_image(item), "https://cdn.test/declared.jpg")

    def test_falls_back_to_the_description_body(self):
        item = self.item(
            """<item>
                 <link>https://example.com/a</link>
                 <description>&lt;p&gt;x&lt;/p&gt;&lt;img src="https://cdn.test/body.jpg"&gt;</description>
               </item>"""
        )
        self.assertEqual(feed_item_image(item), "https://cdn.test/body.jpg")

    def test_reads_content_encoded_too(self):
        # WordPress puts the full post, and its picture, only in content:encoded.
        item = self.item(
            """<item xmlns:content="http://purl.org/rss/1.0/modules/content/">
                 <link>https://example.com/a</link>
                 <description>plain text summary</description>
                 <content:encoded>&lt;img src="https://cdn.test/full.jpg"&gt;</content:encoded>
               </item>"""
        )
        self.assertEqual(feed_item_image(item), "https://cdn.test/full.jpg")

    def test_relative_body_image_resolves_against_the_item_link(self):
        item = self.item(
            """<item>
                 <link>https://example.com/posts/one</link>
                 <description>&lt;img src="/img/a.jpg"&gt;</description>
               </item>"""
        )
        self.assertEqual(feed_item_image(item), "https://example.com/img/a.jpg")

    def test_an_item_with_nothing_stays_none(self):
        item = self.item("<item><link>https://example.com/a</link><description>x</description></item>")
        self.assertIsNone(feed_item_image(item))


class FeedparserEntryImageTests(unittest.TestCase):
    def test_falls_back_to_the_content_body(self):
        entry = {
            "link": "https://example.com/a",
            "content": [{"value": '<img src="https://cdn.test/fp.jpg">'}],
        }
        self.assertEqual(feedparser_entry_image(entry), "https://cdn.test/fp.jpg")

    def test_media_content_still_wins(self):
        entry = {
            "link": "https://example.com/a",
            "media_content": [{"url": "https://cdn.test/declared.jpg", "medium": "image"}],
            "summary": '<img src="https://cdn.test/body.jpg">',
        }
        self.assertEqual(feedparser_entry_image(entry), "https://cdn.test/declared.jpg")

    def test_nothing_anywhere_stays_none(self):
        self.assertIsNone(feedparser_entry_image({"link": "https://example.com/a", "summary": "text"}))


if __name__ == "__main__":
    unittest.main()
