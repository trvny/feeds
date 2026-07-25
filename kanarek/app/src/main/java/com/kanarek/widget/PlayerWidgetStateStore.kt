package com.kanarek.widget

import android.content.Context
import com.kanarek.data.Station
import com.kanarek.data.StationKind

internal class PlayerWidgetStateStore(context: Context) {
    private val preferences =
        context.applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun save(state: PlayerWidgetState) {
        preferences.edit().apply {
            putBoolean(KEY_PLAYING, state.isPlaying)
            putString(KEY_ERROR, state.errorText)
            putString(KEY_NOW_PLAYING, state.nowPlaying)
            val station = state.station
            putBoolean(KEY_HAS_STATION, station != null)
            if (station == null) {
                STATION_KEYS.forEach { remove(it) }
            } else {
                putString(KEY_STATION_ID, station.id)
                putString(KEY_STATION_NAME, station.name)
                putString(KEY_STATION_URL, station.streamUrl)
                putString(KEY_STATION_LOGO, station.logoUrl)
                putString(KEY_STATION_GROUP, station.groupTitle)
                putString(KEY_STATION_KIND, station.kind.name)
            }
        }.apply()
    }

    fun load(): PlayerWidgetState? {
        if (!preferences.contains(KEY_PLAYING)) return null
        return PlayerWidgetState(
            station = loadStation(),
            isPlaying = preferences.getBoolean(KEY_PLAYING, false),
            errorText = preferences.getString(KEY_ERROR, null),
            nowPlaying = preferences.getString(KEY_NOW_PLAYING, null),
        )
    }

    private fun loadStation(): Station? {
        if (!preferences.getBoolean(KEY_HAS_STATION, false)) return null
        val id = preferences.getString(KEY_STATION_ID, null)
        val name = preferences.getString(KEY_STATION_NAME, null)
        val url = preferences.getString(KEY_STATION_URL, null)
        if (id == null || name == null || url == null) return null
        return Station(
            id = id,
            name = name,
            streamUrl = url,
            logoUrl = preferences.getString(KEY_STATION_LOGO, null),
            groupTitle = preferences.getString(KEY_STATION_GROUP, null),
            kind =
                runCatching {
                    StationKind.valueOf(
                        preferences.getString(KEY_STATION_KIND, null).orEmpty(),
                    )
                }.getOrDefault(StationKind.UNKNOWN),
        )
    }

    private companion object {
        const val PREFERENCES_NAME = "player_widget_state"
        const val KEY_PLAYING = "playing"
        const val KEY_ERROR = "error"
        const val KEY_NOW_PLAYING = "now_playing"
        const val KEY_HAS_STATION = "has_station"
        const val KEY_STATION_ID = "station_id"
        const val KEY_STATION_NAME = "station_name"
        const val KEY_STATION_URL = "station_url"
        const val KEY_STATION_LOGO = "station_logo"
        const val KEY_STATION_GROUP = "station_group"
        const val KEY_STATION_KIND = "station_kind"
        val STATION_KEYS =
            listOf(
                KEY_STATION_ID,
                KEY_STATION_NAME,
                KEY_STATION_URL,
                KEY_STATION_LOGO,
                KEY_STATION_GROUP,
                KEY_STATION_KIND,
            )
    }
}
