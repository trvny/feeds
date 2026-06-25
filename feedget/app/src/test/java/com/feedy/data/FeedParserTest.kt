package com.feedy.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure-JVM unit tests for the regex RSS/Atom parser — no Android deps. */
class FeedParserTest {

    private val rss = """
        <?xml version="1.0"?>
        <rss version="2.0"><channel>
          <title>Example News</title>
          <item>
            <title>First &amp; foremost</title>
            <link>https://example.com/a</link>
            <description><![CDATA[<p>Body <b>one</b></p>]]></description>
            <pubDate>Wed, 01 Jan 2020 00:00:00 +0000</pubDate>
            <enclosure url="https://img.example.com/a.jpg" type="image/jpeg"/>
          </item>
          <item>
            <title>Second</title>
            <link>https://example.com/b</link>
            <pubDate>Thu, 02 Jan 2020 00:00:00 +0000</pubDate>
          </item>
        </channel></rss>
    """.trimIndent()

    @Test
    fun parsesRssTitleLinkSummary() {
        val items = FeedParser.parse(rss)
        assertEquals(2, items.size)
        assertEquals("First & foremost", items[0].title)
        assertEquals("https://example.com/a", items[0].link)
        assertEquals("Body one", items[0].summary)
    }

    @Test
    fun derivesSourceFromChannelTitle() {
        assertEquals("Example News", FeedParser.parse(rss)[0].source)
    }

    @Test
    fun parsesRfc822Date() {
        // Wed, 01 Jan 2020 00:00:00 +0000 == 1577836800000
        assertEquals(1577836800000L, FeedParser.parse(rss)[0].publishedAtMillis)
    }

    @Test
    fun picksEnclosureImage() {
        assertEquals("https://img.example.com/a.jpg", FeedParser.parse(rss)[0].imageUrl)
    }

    @Test
    fun dropsItemsMissingTitleOrLink() {
        val broken = """
            <rss><channel><title>X</title>
              <item><link>https://x/1</link></item>
              <item><title>ok</title><link>https://x/2</link></item>
            </channel></rss>
        """.trimIndent()
        val items = FeedParser.parse(broken)
        assertEquals(listOf("https://x/2"), items.map { it.link })
    }

    @Test
    fun parsesAtomEntry() {
        val atom = """
            <?xml version="1.0"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <title>Atom Source</title>
              <entry>
                <title>Hello</title>
                <link rel="alternate" href="https://atom.example/post"/>
                <summary>Short summary</summary>
                <updated>2021-06-15T12:00:00Z</updated>
                <media:content url="https://atom.example/p.png"/>
              </entry>
            </feed>
        """.trimIndent()
        val items = FeedParser.parse(atom)
        assertEquals(1, items.size)
        assertEquals("Hello", items[0].title)
        assertEquals("https://atom.example/post", items[0].link)
        assertEquals("Short summary", items[0].summary)
        assertEquals("https://atom.example/p.png", items[0].imageUrl)
        assertEquals(1623758400000L, items[0].publishedAtMillis)
    }

    @Test
    fun returnsEmptyOnGarbageWithoutThrowing() {
        assertTrue(FeedParser.parse("not xml at all").isEmpty())
        assertTrue(FeedParser.parse("").isEmpty())
    }

    @Test
    fun decodesNumericAndHexEntities() {
        val xml = """
            <rss><channel><title>S</title>
              <item><title>A&#65;&#x42;</title><link>https://x/1</link></item>
            </channel></rss>
        """.trimIndent()
        assertEquals("AAB", FeedParser.parse(xml)[0].title)
    }

    @Test
    fun relativeTimeBuckets() {
        val now = 1_000_000_000_000L
        assertEquals("", FeedParser.relativeTime(null, now))
        assertEquals("just now", FeedParser.relativeTime(now - 30_000, now))
        assertEquals("5m ago", FeedParser.relativeTime(now - 5 * 60_000, now))
        assertEquals("3h ago", FeedParser.relativeTime(now - 3 * 3_600_000, now))
        assertEquals("2d ago", FeedParser.relativeTime(now - 2 * 86_400_000L, now))
    }

    @Test
    fun nullDateWhenUnparseable() {
        val xml = """
            <rss><channel><title>S</title>
              <item><title>t</title><link>https://x/1</link><pubDate>not a date</pubDate></item>
            </channel></rss>
        """.trimIndent()
        assertNull(FeedParser.parse(xml)[0].publishedAtMillis)
    }
}
