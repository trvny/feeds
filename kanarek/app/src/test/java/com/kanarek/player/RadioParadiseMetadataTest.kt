package com.kanarek.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RadioParadiseMetadataTest {
    @Test
    fun mapsBundledMixUrls() {
        assertEquals(0, radioParadiseChannel("http://stream-uk1.radioparadise.com/aac-320"))
        assertEquals(1, radioParadiseChannel("http://stream.radioparadise.com/ogg-192m"))
        assertEquals(2, radioParadiseChannel("http://stream.radioparadise.com/rock-320"))
        assertEquals(3, radioParadiseChannel("http://stream.radioparadise.com/global-320"))
        assertNull(radioParadiseChannel("https://example.com/radioparadise/rock-320"))
    }

    @Test
    fun parsesTrackAndPreferredArtwork() {
        val metadata =
            parseRadioParadiseMetadata(
                """
                {
                  "time": 132,
                  "artist": "KT Tunstall",
                  "title": "Other Side of the World",
                  "album": "Eye to the Telescope",
                  "cover": "https:\/\/img.radioparadise.com\/covers\/l\/large.jpg",
                  "cover_med": "https:\/\/img.radioparadise.com\/covers\/m\/medium.jpg"
                }
                """.trimIndent(),
            )

        requireNotNull(metadata)
        assertEquals("KT Tunstall — Other Side of the World", metadata.displayText)
        assertEquals("Eye to the Telescope", metadata.album)
        assertEquals(
            "https://img.radioparadise.com/covers/m/medium.jpg",
            metadata.artworkUrl,
        )
        assertEquals(134_000L, metadata.refreshAfterMillis)
    }

    @Test
    fun rejectsForeignArtworkAndClampsRefresh() {
        val metadata =
            parseRadioParadiseMetadata(
                """{"time":1,"artist":"Artist","title":"Track","cover":"https://example.com/a.jpg"}""",
            )

        requireNotNull(metadata)
        assertNull(metadata.artworkUrl)
        assertEquals(15_000L, metadata.refreshAfterMillis)
    }

    @Test
    fun rejectsEmptyOrMalformedMetadata() {
        assertNull(parseRadioParadiseMetadata("{}"))
        assertNull(parseRadioParadiseMetadata("not json"))
    }
}
