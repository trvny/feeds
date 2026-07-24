package com.kanarek.ui

import com.kanarek.data.Station
import com.kanarek.data.StationKind

internal enum class StationFilter {
    FAVORITES,
    RADIO,
    TV,
    OTHER,
}

internal data class PlayerScreenUiState(
    val filter: StationFilter = StationFilter.RADIO,
    val editingStation: Station? = null,
    val addDialogVisible: Boolean = false,
    val discoveryDialogVisible: Boolean = false,
    val menuExpanded: Boolean = false,
) {
    fun withValidFilter(tabs: List<StationFilter>): PlayerScreenUiState =
        copy(filter = validStationFilter(filter, tabs))

    fun followCurrentStation(
        station: Station?,
        favoriteIds: Set<String>,
        tabs: List<StationFilter>,
    ): PlayerScreenUiState =
        copy(filter = playerFilterForStation(station, filter, favoriteIds, tabs))
}

internal fun stationTabs(
    stations: List<Station>,
    favoriteIds: Set<String>,
): List<StationFilter> =
    buildList {
        if (stations.any { it.id in favoriteIds }) add(StationFilter.FAVORITES)
        if (stations.any { it.kind == StationKind.RADIO }) add(StationFilter.RADIO)
        if (stations.any { it.kind == StationKind.TV }) add(StationFilter.TV)
        if (stations.any { it.kind == StationKind.UNKNOWN }) add(StationFilter.OTHER)
    }

internal fun validStationFilter(
    selected: StationFilter,
    tabs: List<StationFilter>,
): StationFilter =
    when {
        tabs.isEmpty() -> selected
        selected in tabs -> selected
        else -> tabs.firstOrNull { it != StationFilter.FAVORITES } ?: tabs.first()
    }

internal fun playerFilterForStation(
    station: Station?,
    selected: StationFilter,
    favoriteIds: Set<String>,
    tabs: List<StationFilter>,
): StationFilter {
    station ?: return selected
    if (selected == StationFilter.FAVORITES && station.id in favoriteIds) return selected
    val target =
        when (station.kind) {
            StationKind.TV -> StationFilter.TV
            StationKind.RADIO -> StationFilter.RADIO
            StationKind.UNKNOWN -> StationFilter.OTHER
        }
    return target.takeIf { it in tabs } ?: validStationFilter(selected, tabs)
}

internal fun visibleStations(
    stations: List<Station>,
    favoriteIds: Set<String>,
    filter: StationFilter,
    showTabs: Boolean,
): List<Station> =
    if (!showTabs) {
        stations
    } else {
        when (filter) {
            StationFilter.FAVORITES -> stations.filter { it.id in favoriteIds }
            StationFilter.TV -> stations.filter { it.kind == StationKind.TV }
            StationFilter.RADIO -> stations.filter { it.kind == StationKind.RADIO }
            StationFilter.OTHER -> stations.filter { it.kind == StationKind.UNKNOWN }
        }
    }

/** Bucket a flat station list by non-blank group title, preserving insertion order. */
internal fun groupStations(stations: List<Station>): List<Pair<String?, List<Station>>> {
    val order = LinkedHashMap<String?, MutableList<Station>>()
    for (station in stations) {
        val group = station.groupTitle?.takeIf(String::isNotBlank)
        order.getOrPut(group) { mutableListOf() }.add(station)
    }
    return order.entries.map { it.key to it.value.toList() }
}
