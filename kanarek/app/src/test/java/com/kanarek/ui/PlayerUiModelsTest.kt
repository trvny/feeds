package com.kanarek.ui

import com.kanarek.data.Station
import com.kanarek.data.StationKind
import org.junit.Assert.assertEquals
import org.junit.Test

class PlayerUiModelsTest {
    @Test
    fun tabsReflectAvailableKindsAndFavorites() {
        val radio = station("radio", StationKind.RADIO)
        val tv = station("tv", StationKind.TV)
        val unknown = station("other", StationKind.UNKNOWN)

        assertEquals(
            listOf(
                StationFilter.FAVORITES,
                StationFilter.RADIO,
                StationFilter.TV,
                StationFilter.OTHER,
            ),
            stationTabs(listOf(radio, tv, unknown), favoriteIds = setOf(tv.id)),
        )
    }

    @Test
    fun disappearingFavoritesFallBackToFirstMediaKind() {
        val tabs = listOf(StationFilter.RADIO, StationFilter.TV)

        assertEquals(
            StationFilter.RADIO,
            validStationFilter(StationFilter.FAVORITES, tabs),
        )
    }

    @Test
    fun currentStationMovesListToMatchingKind() {
        val radio = station("radio", StationKind.RADIO)
        val tv = station("tv", StationKind.TV)
        val tabs = listOf(StationFilter.RADIO, StationFilter.TV)

        assertEquals(
            StationFilter.TV,
            playerFilterForStation(
                station = tv,
                selected = StationFilter.RADIO,
                favoriteIds = emptySet(),
                tabs = tabs,
            ),
        )
        assertEquals(
            StationFilter.RADIO,
            playerFilterForStation(
                station = radio,
                selected = StationFilter.TV,
                favoriteIds = emptySet(),
                tabs = tabs,
            ),
        )
    }

    @Test
    fun favoriteCurrentStationKeepsFavoritesTab() {
        val radio = station("radio", StationKind.RADIO)

        assertEquals(
            StationFilter.FAVORITES,
            playerFilterForStation(
                station = radio,
                selected = StationFilter.FAVORITES,
                favoriteIds = setOf(radio.id),
                tabs = listOf(StationFilter.FAVORITES, StationFilter.RADIO),
            ),
        )
    }

    @Test
    fun visibleStationsUseSelectedSliceOnlyWhenTabsAreShown() {
        val radio = station("radio", StationKind.RADIO)
        val tv = station("tv", StationKind.TV)
        val stations = listOf(radio, tv)

        assertEquals(
            listOf(tv),
            visibleStations(
                stations = stations,
                favoriteIds = emptySet(),
                filter = StationFilter.TV,
                showTabs = true,
            ),
        )
        assertEquals(
            stations,
            visibleStations(
                stations = stations,
                favoriteIds = emptySet(),
                filter = StationFilter.TV,
                showTabs = false,
            ),
        )
    }

    @Test
    fun groupsPreserveFirstSeenOrderAndUngroupedBucket() {
        val first = station("first", StationKind.RADIO, group = "News")
        val ungrouped = station("ungrouped", StationKind.RADIO)
        val second = station("second", StationKind.RADIO, group = "News")

        assertEquals(
            listOf(
                "News" to listOf(first, second),
                null to listOf(ungrouped),
            ),
            groupStations(listOf(first, ungrouped, second)),
        )
    }

    private fun station(
        name: String,
        kind: StationKind,
        group: String? = null,
    ): Station =
        Station(
            id = name,
            name = name,
            streamUrl = "https://example.com/$name",
            logoUrl = null,
            groupTitle = group,
            tvgId = null,
            userAgent = null,
            referrer = null,
            kind = kind,
        )
}
