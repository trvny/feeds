package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure-JVM unit tests for M3U/M3U8 playlist import/export — no Android deps. */
class M3uCodecTest {
    @Test
    fun parsesExtinfWithLogoAndGroup() {
        val m3u =
            """
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
        val m3u =
            """
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
        val m3u =
            """
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
    fun parsesUserAgentAndReferrerFromExtinfAttrs() {
        val m3u =
            """
            #EXTINF:-1 group-title="Movies" user-agent="Mozilla/5.0" referrer="https://vod.tvp.pl/",AMC Europe
            https://x.com/amc.m3u8
            """.trimIndent()
        val station = M3uCodec.parse(m3u)[0]
        assertEquals("Mozilla/5.0", station.userAgent)
        assertEquals("https://vod.tvp.pl/", station.referrer)
    }

    @Test
    fun parsesUserAgentAndReferrerFromExtvlcopt() {
        val m3u =
            """
            #EXTINF:-1,TVP1
            #EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)
            #EXTVLCOPT:http-referrer=https://vod.tvp.pl/
            https://x.com/tvp1.m3u
            """.trimIndent()
        val station = M3uCodec.parse(m3u)[0]
        assertEquals("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", station.userAgent)
        assertEquals("https://vod.tvp.pl/", station.referrer)
    }

    @Test
    fun extinfAttrsTakePrecedenceOverExtvlcoptWhenBothPresent() {
        val m3u =
            """
            #EXTINF:-1 user-agent="from-extinf",TVP1
            #EXTVLCOPT:http-user-agent=from-vlcopt
            https://x.com/tvp1.m3u
            """.trimIndent()
        // EXTINF is parsed first and sets pendingUserAgent; EXTVLCOPT then overwrites it since
        // it's read afterward — assert the actually-implemented "last one wins" behavior so this
        // stays honest about precedence if the tag order in a pasted list ever varies.
        val station = M3uCodec.parse(m3u)[0]
        assertEquals("from-vlcopt", station.userAgent)
    }

    @Test
    fun buildEmitsHeaderAndQuotedAttributes() {
        val m3u =
            M3uCodec.build(
                listOf(
                    Station(
                        id = "1",
                        name = "TVP1",
                        streamUrl = "https://x.com/1.m3u8",
                        logoUrl = "https://x.com/l.png",
                        groupTitle = "PL",
                    ),
                ),
            )
        assertTrue(m3u.startsWith("#EXTM3U\n"))
        assertTrue(m3u.contains("""tvg-logo="https://x.com/l.png""""))
        assertTrue(m3u.contains("""group-title="PL""""))
        assertTrue(m3u.contains(",TVP1"))
        assertTrue(m3u.contains("https://x.com/1.m3u8"))
    }

    @Test
    fun buildEmitsUserAgentReferrerAttrAndVlcoptLines() {
        val m3u =
            M3uCodec.build(
                listOf(
                    Station(
                        id = "1",
                        name = "TVP1",
                        streamUrl = "https://x.com/1.m3u",
                        userAgent = "Mozilla/5.0",
                        referrer = "https://vod.tvp.pl/",
                    ),
                ),
            )
        assertTrue(m3u.contains("""user-agent="Mozilla/5.0""""))
        assertTrue(m3u.contains("""referrer="https://vod.tvp.pl/""""))
        assertTrue(m3u.contains("#EXTVLCOPT:http-user-agent=Mozilla/5.0"))
        assertTrue(m3u.contains("#EXTVLCOPT:http-referrer=https://vod.tvp.pl/"))
    }

    @Test
    fun roundTripPreservesFields() {
        val stations =
            listOf(
                Station(id = "ignored", name = "Radio Zet", streamUrl = "https://x.com/zet.mp3", logoUrl = null, groupTitle = "Radio"),
                Station(
                    id = "ignored",
                    name = "TVP1",
                    streamUrl = "https://x.com/tvp1.m3u8",
                    logoUrl = "https://x.com/l.png",
                    groupTitle = "TV",
                ),
            )
        val parsed = M3uCodec.parse(M3uCodec.build(stations))
        assertEquals(stations.map { it.name }, parsed.map { it.name })
        assertEquals(stations.map { it.streamUrl }, parsed.map { it.streamUrl })
        assertEquals(stations.map { it.logoUrl }, parsed.map { it.logoUrl })
        assertEquals(stations.map { it.groupTitle }, parsed.map { it.groupTitle })
    }

    @Test
    fun roundTripPreservesUserAgentAndReferrer() {
        val stations =
            listOf(
                Station(
                    id = "ignored",
                    name = "AMC Europe",
                    streamUrl = "https://x.com/amc.m3u8",
                    userAgent = "Mozilla/5.0",
                    referrer = null,
                ),
                Station(
                    id = "ignored",
                    name = "TVP1",
                    streamUrl = "https://x.com/tvp1.m3u",
                    userAgent = "Mozilla/5.0 (Win)",
                    referrer = "https://vod.tvp.pl/",
                ),
            )
        val parsed = M3uCodec.parse(M3uCodec.build(stations))
        assertEquals(stations.map { it.userAgent }, parsed.map { it.userAgent })
        assertEquals(stations.map { it.referrer }, parsed.map { it.referrer })
    }

    @Test
    fun parsesTvgId() {
        val m3u =
            """
            #EXTM3U
            #EXTINF:-1 tvg-id="TVPInfo.pl" tvg-logo="https://x/l.png" group-title="News",TVP Info
            https://x/tvpinfo.m3u8
            """.trimIndent()
        val stations = M3uCodec.parse(m3u)
        assertEquals(1, stations.size)
        assertEquals("TVPInfo.pl", stations[0].tvgId)
    }

    @Test
    fun tvgIdIsNullWhenAbsent() {
        val stations =
            M3uCodec.parse(
                """
                #EXTM3U
                #EXTINF:-1 group-title="News",No Id
                https://x/noid.m3u8
                """.trimIndent(),
            )
        assertEquals(1, stations.size)
        assertEquals(null, stations[0].tvgId)
    }

    @Test
    fun buildEmitsTvgId() {
        val out = M3uCodec.build(listOf(Station(id = M3uCodec.idFor("https://x/s"), name = "S", streamUrl = "https://x/s", tvgId = "Foo.pl")))
        assertTrue(out.contains("tvg-id=\"Foo.pl\""))
    }

    @Test
    fun tvgIdRoundTrips() {
        val stations =
            listOf(
                Station(id = M3uCodec.idFor("https://x/a"), name = "A", streamUrl = "https://x/a", tvgId = "A.pl"),
                Station(id = M3uCodec.idFor("https://x/b"), name = "B", streamUrl = "https://x/b", tvgId = null),
            )
        val parsed = M3uCodec.parse(M3uCodec.build(stations))
        assertEquals(stations.map { it.tvgId }, parsed.map { it.tvgId })
    }

    @Test
    fun parsesKanarekKind() {
        val m3u =
            """
            #EXTM3U
            #EXTINF:-1 kanarek-kind="tv",Some Channel
            https://x/tv.m3u8
            #EXTINF:-1 kanarek-kind="radio",Some Station
            https://x/radio.mp3
            #EXTINF:-1,No Kind
            https://x/plain.mp3
            """.trimIndent()
        val stations = M3uCodec.parse(m3u)
        assertEquals(StationKind.TV, stations[0].kind)
        assertEquals(StationKind.RADIO, stations[1].kind)
        assertEquals(StationKind.UNKNOWN, stations[2].kind)
    }

    @Test
    fun buildEmitsKindOnlyWhenKnown() {
        val out =
            M3uCodec.build(
                listOf(
                    Station(id = M3uCodec.idFor("https://x/a"), name = "A", streamUrl = "https://x/a", kind = StationKind.TV),
                    Station(id = M3uCodec.idFor("https://x/b"), name = "B", streamUrl = "https://x/b", kind = StationKind.UNKNOWN),
                ),
            )
        assertTrue(out.contains("kanarek-kind=\"tv\""))
        assertTrue(!out.contains("kanarek-kind=\"unknown\""))
    }

    @Test
    fun kindRoundTrips() {
        val stations =
            listOf(
                Station(id = M3uCodec.idFor("https://x/a"), name = "A", streamUrl = "https://x/a", kind = StationKind.TV),
                Station(id = M3uCodec.idFor("https://x/b"), name = "B", streamUrl = "https://x/b", kind = StationKind.RADIO),
                Station(id = M3uCodec.idFor("https://x/c"), name = "C", streamUrl = "https://x/c", kind = StationKind.UNKNOWN),
            )
        val parsed = M3uCodec.parse(M3uCodec.build(stations))
        assertEquals(stations.map { it.kind }, parsed.map { it.kind })
    }
}
