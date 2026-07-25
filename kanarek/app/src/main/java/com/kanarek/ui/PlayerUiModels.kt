package com.kanarek.ui

import android.os.Bundle
import androidx.compose.runtime.saveable.Saver
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

internal val PlayerScreenUiStateSaver =
    Saver<PlayerScreenUiState, Bundle>(
        save = { state -> state.toSavedBundle() },
        restore = ::restorePlayerScreenUiState,
    )

internal fun PlayerScreenUiState.toSavedBundle(): Bundle =
    Bundle().apply {
        putString(KEY_FILTER, filter.name)
        putBoolean(KEY_ADD_DIALOG, addDialogVisible)
        putBoolean(KEY_DISCOVERY_DIALOG, discoveryDialogVisible)
        putBoolean(KEY_MENU_EXPANDED, menuExpanded)
        editingStation?.let { station ->
            putBoolean(KEY_HAS_EDITING_STATION, true)
            putString(KEY_STATION_ID, station.id)
            putString(KEY_STATION_NAME, station.name)
            putString(KEY_STATION_URL, station.streamUrl)
            putString(KEY_STATION_LOGO, station.logoUrl)
            putString(KEY_STATION_GROUP, station.groupTitle)
            putString(KEY_STATION_TVG_ID, station.tvgId)
            putString(KEY_STATION_USER_AGENT, station.userAgent)
            putString(KEY_STATION_REFERRER, station.referrer)
            putString(KEY_STATION_KIND, station.kind.name)
        }
    }

internal fun restorePlayerScreenUiState(saved: Bundle): PlayerScreenUiState =
    PlayerScreenUiState(
        filter = saved.enumValue(KEY_FILTER, StationFilter.RADIO),
        editingStation = saved.restoreEditingStation(),
        addDialogVisible = saved.getBoolean(KEY_ADD_DIALOG),
        discoveryDialogVisible = saved.getBoolean(KEY_DISCOVERY_DIALOG),
        menuExpanded = saved.getBoolean(KEY_MENU_EXPANDED),
    )

private fun Bundle.restoreEditingStation(): Station? {
    if (!getBoolean(KEY_HAS_EDITING_STATION)) return null
    val id = getString(KEY_STATION_ID).orEmpty()
    val name = getString(KEY_STATION_NAME).orEmpty()
    val streamUrl = getString(KEY_STATION_URL).orEmpty()
    if (id.isBlank() || streamUrl.isBlank()) return null
    return Station(
        id = id,
        name = name,
        streamUrl = streamUrl,
        logoUrl = getString(KEY_STATION_LOGO),
        groupTitle = getString(KEY_STATION_GROUP),
        tvgId = getString(KEY_STATION_TVG_ID),
        userAgent = getString(KEY_STATION_USER_AGENT),
        referrer = getString(KEY_STATION_REFERRER),
        kind = enumValue(KEY_STATION_KIND, StationKind.UNKNOWN),
    )
}

private inline fun <reified T : Enum<T>> Bundle.enumValue(
    key: String,
    fallback: T,
): T =
    getString(key)
        ?.let { value -> enumValues<T>().firstOrNull { it.name == value } }
        ?: fallback

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

private const val KEY_FILTER = "filter"
private const val KEY_ADD_DIALOG = "addDialog"
private const val KEY_DISCOVERY_DIALOG = "discoveryDialog"
private const val KEY_MENU_EXPANDED = "menuExpanded"
private const val KEY_HAS_EDITING_STATION = "hasEditingStation"
private const val KEY_STATION_ID = "stationId"
private const val KEY_STATION_NAME = "stationName"
private const val KEY_STATION_URL = "stationUrl"
private const val KEY_STATION_LOGO = "stationLogo"
private const val KEY_STATION_GROUP = "stationGroup"
private const val KEY_STATION_TVG_ID = "stationTvgId"
private const val KEY_STATION_USER_AGENT = "stationUserAgent"
private const val KEY_STATION_REFERRER = "stationReferrer"
private const val KEY_STATION_KIND = "stationKind"
