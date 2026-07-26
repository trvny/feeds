package com.kanarek.widget

import com.kanarek.data.Station
import com.kanarek.data.StationKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PlayerWidgetStateStoreTest {
    private val store: PlayerWidgetStateStore
        get() = PlayerWidgetStateStore(RuntimeEnvironment.getApplication())

    @Test
    fun `persisted widget state restores only the station`() {
        val station =
            Station(
                id = "radio",
                name = "Radio Example",
                streamUrl = "https://example.com/live",
                logoUrl = "https://example.com/logo.png",
                groupTitle = "Music",
                kind = StationKind.RADIO,
            )
        store.save(
            PlayerWidgetState(
                station = station,
                isPlaying = true,
                errorText = "offline",
                nowPlaying = "Artist — Track",
            ),
        )

        assertEquals(
            PlayerWidgetState(station = station, isPlaying = false),
            store.load(),
        )
    }

    @Test
    fun `saving empty state removes previous station`() {
        store.save(
            PlayerWidgetState(
                station =
                    Station(
                        id = "tv",
                        name = "TV Example",
                        streamUrl = "https://example.com/tv",
                    ),
                isPlaying = true,
            ),
        )
        store.save(PlayerWidgetState(station = null, isPlaying = false, errorText = "offline"))

        val restored = store.load()
        assertNull(restored?.station)
        assertEquals(false, restored?.isPlaying)
        assertNull(restored?.errorText)
    }
}
