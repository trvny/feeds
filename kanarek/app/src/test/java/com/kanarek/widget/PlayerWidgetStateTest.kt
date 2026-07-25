package com.kanarek.widget

import com.kanarek.data.Station
import com.kanarek.data.StationKind
import org.junit.Assert.assertEquals
import org.junit.Test

class PlayerWidgetStateTest {
    private val station =
        Station(
            id = "radio",
            name = "Radio Example",
            streamUrl = "https://example.com/live",
            groupTitle = "News",
            kind = StationKind.RADIO,
        )

    @Test
    fun `live metadata replaces station group`() {
        assertEquals(
            "Artist — Track",
            playerWidgetSubtitle(
                PlayerWidgetState(
                    station = station,
                    isPlaying = true,
                    nowPlaying = "Artist — Track",
                ),
            ),
        )
    }

    @Test
    fun `playback error replaces live metadata`() {
        assertEquals(
            "Retry playback",
            playerWidgetSubtitle(
                PlayerWidgetState(
                    station = station,
                    isPlaying = false,
                    errorText = "Retry playback",
                    nowPlaying = "Artist — Track",
                ),
            ),
        )
    }
}
