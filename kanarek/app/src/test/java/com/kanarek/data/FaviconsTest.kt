package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure-JVM unit tests for the favicon logo-fallback helper — no Android deps. */
class FaviconsTest {
    @Test
    fun extractsHostLowercasedWithoutPortOrWww() {
        assertEquals("rmf.fm", Favicons.hostOf("https://www.RMF.fm:8443/stream/aac"))
        assertEquals("stream.polskieradio.pl", Favicons.hostOf("http://stream.polskieradio.pl/pr1"))
    }

    @Test
    fun rejectsNonHttpAndGarbage() {
        assertNull(Favicons.hostOf("rtsp://10.0.0.1/live"))
        assertNull(Favicons.hostOf("not a url"))
        assertNull(Favicons.hostOf(""))
    }

    @Test
    fun chainPutsExplicitLogoFirstThenGoogleThenDdg() {
        val s =
            Station(
                id = "x",
                name = "RMF",
                streamUrl = "https://stream.rmf.fm/aac",
                logoUrl = "https://cdn.example/rmf.png",
            )
        val chain = Favicons.logoChain(s)
        assertEquals(3, chain.size)
        assertEquals("https://cdn.example/rmf.png", chain[0])
        assertTrue(chain[1].startsWith("https://www.google.com/s2/favicons?domain=stream.rmf.fm"))
        assertEquals("https://icons.duckduckgo.com/ip3/stream.rmf.fm.ico", chain[2])
    }

    @Test
    fun chainWithoutLogoStartsAtFavicons() {
        val s = Station(id = "x", name = "R", streamUrl = "https://radio.example/live.mp3")
        val chain = Favicons.logoChain(s)
        assertEquals(2, chain.size)
        assertTrue(chain[0].contains("google.com/s2/favicons"))
    }

    @Test
    fun unparseableStreamYieldsOnlyExplicitLogoOrNothing() {
        val bare = Station(id = "x", name = "R", streamUrl = "rtsp://weird/live")
        assertTrue(Favicons.logoChain(bare).isEmpty())
        assertNull(Favicons.firstFor("rtsp://weird/live"))
    }
}
