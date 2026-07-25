package com.kanarek.player

import com.kanarek.data.Station
import com.kanarek.data.StationKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NowPlayingMetadataTest {
    private val station =
        Station(
            id = "radio",
            name = "Radio Example",
            streamUrl = "https://example.com/live",
            groupTitle = "News",
            kind = StationKind.RADIO,
        )

    @Test
    fun `dynamic artist and title are combined`() {
        assertEquals(
            "Artist — Track",
            streamMetadataText(station, title = " Track ", artist = " Artist "),
        )
    }

    @Test
    fun `static station metadata is ignored`() {
        assertNull(
            streamMetadataText(
                station,
                title = station.name,
                artist = station.groupTitle,
            ),
        )
    }

    @Test
    fun `dynamic title survives static station artist`() {
        assertEquals(
            "Live programme",
            streamMetadataText(station, title = "Live programme", artist = station.groupTitle),
        )
    }
}
