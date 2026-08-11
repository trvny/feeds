package com.kanarek.ui

import android.os.Bundle
import com.kanarek.data.Station
import com.kanarek.data.StationKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PlayerStateRestorationTest {
    @Test
    fun `editing station and selected filter survive while transient menu resets`() {
        val station =
            Station(
                id = "station-1",
                name = "Example TV",
                streamUrl = "https://example.com/live.m3u8",
                logoUrl = "https://example.com/logo.png",
                groupTitle = "News",
                tvgId = "example.tv",
                userAgent = "Kanarek",
                referrer = "https://example.com",
                kind = StationKind.TV,
            )
        val state =
            PlayerScreenUiState(
                filter = StationFilter.TV,
                editingStation = station,
                menuExpanded = true,
            )
        val restored = restorePlayerScreenUiState(state.toSavedBundle())

        assertEquals(state.copy(menuExpanded = false), restored)
    }

    @Test
    fun `open Player dialogs survive state restoration`() {
        val state =
            PlayerScreenUiState(
                addDialogVisible = true,
                discoveryDialogVisible = true,
            )
        val restored = restorePlayerScreenUiState(state.toSavedBundle())

        assertEquals(state, restored)
    }

    @Test
    fun `invalid editing station payload is discarded`() {
        val saved =
            Bundle().apply {
                putString("filter", StationFilter.FAVORITES.name)
                putBoolean("hasEditingStation", true)
                putString("stationId", "station-1")
            }
        val restored = restorePlayerScreenUiState(saved)

        assertEquals(StationFilter.FAVORITES, restored.filter)
        assertNull(restored.editingStation)
    }
}
