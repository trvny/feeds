package com.feedy.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure-JVM unit tests for OPML import/export — no Android deps. */
class OpmlTest {

    @Test
    fun parsesXmlUrlDoubleAndSingleQuotes() {
        val opml = """
            <opml version="2.0"><body>
              <outline type="rss" xmlUrl="https://a.com/feed"/>
              <outline type='rss' xmlUrl='https://b.com/feed'/>
            </body></opml>
        """.trimIndent()
        assertEquals(listOf("https://a.com/feed", "https://b.com/feed"), Opml.parse(opml))
    }

    @Test
    fun dedupesPreservingFirstOccurrenceOrder() {
        val opml = """
            <opml><body>
              <outline xmlUrl="https://a/1"/>
              <outline xmlUrl="https://b/2"/>
              <outline xmlUrl="https://a/1"/>
            </body></opml>
        """.trimIndent()
        assertEquals(listOf("https://a/1", "https://b/2"), Opml.parse(opml))
    }

    @Test
    fun unescapesEntitiesInUrl() {
        val opml = """<opml><body><outline xmlUrl="https://x.com/?a=1&amp;b=2"/></body></opml>"""
        assertEquals(listOf("https://x.com/?a=1&b=2"), Opml.parse(opml))
    }

    @Test
    fun returnsEmptyOnMalformedInput() {
        assertTrue(Opml.parse("totally not opml").isEmpty())
        assertTrue(Opml.parse("").isEmpty())
    }

    @Test
    fun buildEscapesAmpersandAndEmitsXmlUrl() {
        val xml = Opml.build(listOf("https://x.com/?a=1&b=2"))
        assertTrue(xml.contains("""xmlUrl="https://x.com/?a=1&amp;b=2""""))
        assertTrue(xml.contains("<opml version=\"2.0\">"))
    }

    @Test
    fun buildLabelsUseHostWithoutWww() {
        val xml = Opml.build(listOf("https://www.example.com/feed"))
        assertTrue(xml.contains("""text="example.com""""))
    }

    @Test
    fun roundTripPreservesOrderAndUrls() {
        val feeds = listOf("https://a.com/x", "https://b.com/y", "https://x.com/?a=1&b=2")
        assertEquals(feeds, Opml.parse(Opml.build(feeds)))
    }
}
