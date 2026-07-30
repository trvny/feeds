import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import youtubs  # noqa: E402


FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
  <title>Videos</title>
  <author><name>Example Channel</name></author>
  <entry>
    <yt:videoId>normal123</yt:videoId>
    <title>Normal video</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=normal123"/>
    <published>2026-07-29T12:00:00+00:00</published>
    <updated>2026-07-29T13:00:00+00:00</updated>
    <media:group>
      <media:description>A proper long-form video.</media:description>
      <media:thumbnail url="https://i.ytimg.com/vi/normal123/hqdefault.jpg"/>
    </media:group>
  </entry>
</feed>
"""


class YouTubsTests(unittest.TestCase):
    def test_channel_ids_are_unique_and_derive_non_shorts_feeds(self):
        self.assertEqual(len(youtubs.CHANNEL_IDS), 18)
        self.assertEqual(len(set(youtubs.CHANNEL_IDS)), 18)
        for channel_id in youtubs.CHANNEL_IDS:
            suffix = channel_id[2:]
            urls = youtubs.channel_feed_urls(channel_id)
            self.assertEqual(
                urls,
                (
                    "https://www.youtube.com/feeds/videos.xml?"
                    f"playlist_id=UULF{suffix}",
                    "https://www.youtube.com/feeds/videos.xml?"
                    f"playlist_id=UULV{suffix}",
                ),
            )
            self.assertTrue(all("rss-bridge" not in url for url in urls))
            self.assertTrue(all("channel_id=" not in url for url in urls))
            self.assertTrue(all("UUSH" not in url for url in urls))

    def test_parser_preserves_channel_metadata(self):
        entries = youtubs.parse_channel_feed(FEED_XML)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Normal video")
        self.assertEqual(entries[0]["source"], "Example Channel")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-07-29T12:00:00+00:00")
        self.assertEqual(entries[0]["description"], "A proper long-form video.")
        self.assertEqual(
            entries[0]["image"],
            "https://i.ytimg.com/vi/normal123/hqdefault.jpg",
        )

    def test_normalized_known_video_is_not_emitted_again(self):
        known = "http://youtube.com/watch?v=normal123&utm_source=feed"

        entries = youtubs.parse_channel_feed(FEED_XML, {known})

        self.assertEqual(entries, [])

    def test_thumbnail_falls_back_to_video_id(self):
        xml = """
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015">
          <title>Videos</title>
          <author><name>No Thumbnail</name></author>
          <entry>
            <yt:videoId>fallback123</yt:videoId>
            <title>Fallback art</title>
            <link rel="alternate" href="https://www.youtube.com/watch?v=fallback123"/>
            <published>2026-07-29T12:00:00Z</published>
          </entry>
        </feed>
        """

        entries = youtubs.parse_channel_feed(xml)

        self.assertEqual(
            entries[0]["image"],
            "https://i.ytimg.com/vi/fallback123/hqdefault.jpg",
        )

    def test_one_failed_channel_does_not_hide_other_channels(self):
        with (
            patch.object(youtubs, "CHANNEL_IDS", ("UCfailed", "UCworking")),
            patch.object(
                youtubs,
                "fetch_youtube_feed",
                side_effect=[None, None, FEED_XML, None],
            ),
        ):
            entries = youtubs.collect_youtubs(set())

        self.assertEqual([entry["title"] for entry in entries], ["Normal video"])


if __name__ == "__main__":
    unittest.main()
