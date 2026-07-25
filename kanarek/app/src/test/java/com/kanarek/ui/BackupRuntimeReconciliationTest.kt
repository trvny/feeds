package com.kanarek.ui

import com.kanarek.data.Station
import com.kanarek.data.StationKind
import org.junit.Assert.assertEquals
import org.junit.Test

class BackupRuntimeReconciliationTest {
    @Test
    fun `imported runtime consumers are all refreshed`() {
        val station =
            Station(
                id = "station-1",
                name = "Example",
                streamUrl = "https://example.com/live.m3u8",
                kind = StationKind.TV,
            )
        val calls = mutableListOf<String>()

        reconcileImportedRuntime(
            state =
                ImportedRuntimeState(
                    readerRefreshMinutes = 60,
                    notificationsEnabled = true,
                    currentStation = station,
                ),
            syncReader = { minutes -> calls += "reader:$minutes" },
            syncNotifications = { enabled -> calls += "notifications:$enabled" },
            refreshNewsWidgets = { calls += "news-widgets" },
            updatePlayerWidgets = { current -> calls += "player-widget:${current?.id}" },
        )

        assertEquals(
            listOf(
                "reader:60",
                "notifications:true",
                "news-widgets",
                "player-widget:station-1",
            ),
            calls,
        )
    }

    @Test
    fun `disabled imported workers are actively reconciled`() {
        val readerIntervals = mutableListOf<Int>()
        val notificationStates = mutableListOf<Boolean>()

        reconcileImportedRuntime(
            state =
                ImportedRuntimeState(
                    readerRefreshMinutes = 0,
                    notificationsEnabled = false,
                    currentStation = null,
                ),
            syncReader = readerIntervals::add,
            syncNotifications = notificationStates::add,
            refreshNewsWidgets = {},
            updatePlayerWidgets = {},
        )

        assertEquals(listOf(0), readerIntervals)
        assertEquals(listOf(false), notificationStates)
    }
}
