package com.feedy.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure-JVM unit tests for the multi-playlist container codec — no Android deps. */
class PlaylistsTest {

    private fun s(name: String, url: String) = Station(id = M3uCodec.idFor(url), name = name, streamUrl = url)

    @Test
    fun roundTripPreservesNamesOrderAndStations() {
        val input = listOf(
            Playlists.Named("Radio", listOf(s("Trójka", "https://x/pr3.m3u8"), s("ZET", "https://x/zet.livx"))),
            Playlists.Named("IPTV", listOf(s("TVP1", "https://x/tvp1.m3u8"))),
        )
        val parsed = Playlists.parse(Playlists.build(input))
        assertEquals(listOf("Radio", "IPTV"), parsed.map { it.name })
        assertEquals(listOf("Trójka", "ZET"), parsed[0].stations.map { it.name })
        assertEquals("https://x/tvp1.m3u8", parsed[1].stations[0].streamUrl)
    }

    @Test
    fun sectionIsValidStandaloneM3u() {
        val built = Playlists.build(listOf(Playlists.Named("Radio", listOf(s("A", "https://x/a.mp3")))))
        val body = built.lines().drop(1).joinToString("\n") // strip the marker line
        assertEquals(listOf("https://x/a.mp3"), M3uCodec.parse(body).map { it.streamUrl })
    }

    @Test
    fun duplicateNamesKeepLast() {
        val text = """
            #FEEDY-PLAYLIST:Radio
            #EXTINF:-1,Old
            https://x/old.mp3
            #FEEDY-PLAYLIST:Radio
            #EXTINF:-1,New
            https://x/new.mp3
        """.trimIndent()
        val parsed = Playlists.parse(text)
        assertEquals(1, parsed.size)
        assertEquals("New", parsed[0].stations[0].name)
    }

    @Test
    fun ignoresContentBeforeFirstMarkerAndEmptyNames() {
        val text = """
            https://stray/url.mp3
            #FEEDY-PLAYLIST:
            https://also/ignored.mp3
            #FEEDY-PLAYLIST:Only
            https://x/kept.mp3
        """.trimIndent()
        val parsed = Playlists.parse(text)
        assertEquals(listOf("Only"), parsed.map { it.name })
        assertEquals("https://x/kept.mp3", parsed[0].stations[0].streamUrl)
    }

    @Test
    fun emptyInputYieldsNoPlaylists() {
        assertTrue(Playlists.parse("").isEmpty())
        assertTrue(Playlists.parse("#EXTM3U\nhttps://x/a.mp3").isEmpty())
    }
}
