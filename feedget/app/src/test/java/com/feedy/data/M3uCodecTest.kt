package com.feedy.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure-JVM unit tests for M3U/M3U8 playlist import/export — no Android deps. */
class M3uCodecTest {

    @Test
    fun parsesExtinfWithLogoAndGroup() {
        val m3u = """
            #EXTM3U
            #EXTINF:-1 tvg-logo="https://x.com/logo.png" group-title="News",TVP Info
            https://x.com/tvpinfo.m3u8
        """.trimIndent()
        val stations = M3uCodec.parse(m3u)
        assertEquals(1, stations.size)
        assertEquals("TVP Info", stations[0].name)
        assertEquals("https://x.com/tvpinfo.m3u8", stations[0].streamUrl)
        assertEquals("https://x.com/logo.png", stations[0].logoUrl)
        assertEquals("News", stations[0].groupTitle)
    }

    @Test
    fun titleWithCommaAfterQuotedAttributesIsNotSplit() {
        val m3u = """
            #EXTINF:-1 group-title="News, Sports",Radio One, 24/7
            https://x.com/radio.mp3
        """.trimIndent()
        val stations = M3uCodec.parse(m3u)
        assertEquals("Radio One, 24/7", stations[0].name)
        assertEquals("News, Sports", stations[0].groupTitle)
    }

    @Test
    fun parsesPlainDurationCommaTitleWithNoAttributes() {
        val m3u = "#EXTINF:-1,Polskie Radio\nhttps://x.com/pr.mp3"
        val stations = M3uCodec.parse(m3u)
        assertEquals("Polskie Radio", stations[0].name)
        assertEquals(null, stations[0].logoUrl)
    }

    @Test
    fun missingExtinfFallsBackToHostAsName() {
        val stations = M3uCodec.parse("https://www.example.com/stream.mp3")
        assertEquals("example.com", stations[0].name)
    }

    @Test
    fun dedupesByStreamUrlKeepingFirst() {
        val m3u = """
            #EXTINF:-1,First
            https://x.com/a.mp3
            #EXTINF:-1,Duplicate
            https://x.com/a.mp3
        """.trimIndent()
        val stations = M3uCodec.parse(m3u)
        assertEquals(1, stations.size)
        assertEquals("First", stations[0].name)
    }

    @Test
    fun returnsEmptyOnMalformedInput() {
        assertTrue(M3uCodec.parse("").isEmpty())
        assertTrue(M3uCodec.parse("# just a comment, no urls").isEmpty())
    }

    @Test
    fun stableIdIsSha1OfStreamUrl() {
        val a = M3uCodec.parse("#EXTINF:-1,A\nhttps://x.com/a.mp3")[0]
        val b = M3uCodec.parse("#EXTINF:-1,Renamed\nhttps://x.com/a.mp3")[0]
        assertEquals(a.id, b.id)
    }

    @Test
    fun buildEmitsHeaderAndQuotedAttributes() {
        val m3u = M3uCodec.build(
            listOf(Station(id = "1", name = "TVP1", streamUrl = "https://x.com/1.m3u8", logoUrl = "https://x.com/l.png", groupTitle = "PL")),
        )
        assertTrue(m3u.startsWith("#EXTM3U\n"))
        assertTrue(m3u.contains("""tvg-logo="https://x.com/l.png""""))
        assertTrue(m3u.contains("""group-title="PL""""))
        assertTrue(m3u.contains(",TVP1"))
        assertTrue(m3u.contains("https://x.com/1.m3u8"))
    }

    @Test
    fun roundTripPreservesFields() {
        val stations = listOf(
            Station(id = "ignored", name = "Radio Zet", streamUrl = "https://x.com/zet.mp3", logoUrl = null, groupTitle = "Radio"),
            Station(id = "ignored", name = "TVP1", streamUrl = "https://x.com/tvp1.m3u8", logoUrl = "https://x.com/l.png", groupTitle = "TV"),
        )
        val parsed = M3uCodec.parse(M3uCodec.build(stations))
        assertEquals(stations.map { it.name }, parsed.map { it.name })
        assertEquals(stations.map { it.streamUrl }, parsed.map { it.streamUrl })
        assertEquals(stations.map { it.logoUrl }, parsed.map { it.logoUrl })
        assertEquals(stations.map { it.groupTitle }, parsed.map { it.groupTitle })
    }
}
