package com.kanarek.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

/**
 * Single app-wide settings store (Preferences DataStore, not SharedPreferences).
 * Keys namespaced in the companion; reads decode defensively.
 */
class SettingsStore(
    private val context: Context,
) {
    val feeds: Flow<List<String>> =
        context.dataStore.data.map { prefs ->
            decodeFeeds(prefs[KEY_FEEDS])
        }

    /** Optional Cloudflare Worker base URL. Blank → parse feeds on-device. */
    val backendUrl: Flow<String> =
        context.dataStore.data.map { prefs ->
            prefs[KEY_BACKEND].orEmpty()
        }

    val intervalSeconds: Flow<Int> =
        context.dataStore.data.map { prefs ->
            prefs[KEY_INTERVAL] ?: DEFAULT_INTERVAL
        }

    /** When true, the widget/showcase shows only ranked headlines (see [Headlines]). Default: all. */
    val headlinesMode: Flow<Boolean> =
        context.dataStore.data.map { prefs ->
            prefs[KEY_HEADLINES] ?: false
        }

    /** User-curated set of cover-worthy source names (case-insensitive). */
    val topSources: Flow<Set<String>> =
        context.dataStore.data.map { prefs ->
            decodeSources(prefs[KEY_TOP_SOURCES])
        }

    /** Radio/IPTV station list (the player screen), stored as M3U text — same format as import/export. */
    val stations: Flow<List<Station>> =
        context.dataStore.data.map { prefs ->
            M3uCodec.parse(prefs[KEY_STATIONS].orEmpty())
        }

    /** Id of the last-played station, so the player/widget resumes where it left off. */
    val lastStationId: Flow<String?> = context.dataStore.data.map { prefs -> prefs[KEY_LAST_STATION] }

    suspend fun setFeeds(raw: String) {
        context.dataStore.edit { it[KEY_FEEDS] = raw.trim() }
    }

    suspend fun setBackendUrl(url: String) {
        context.dataStore.edit { it[KEY_BACKEND] = url.trim() }
    }

    suspend fun setIntervalSeconds(seconds: Int) {
        context.dataStore.edit { it[KEY_INTERVAL] = seconds.coerceIn(3, 120) }
    }

    suspend fun setHeadlinesMode(enabled: Boolean) {
        context.dataStore.edit { it[KEY_HEADLINES] = enabled }
    }

    suspend fun setTopSources(sources: Set<String>) {
        context.dataStore.edit { it[KEY_TOP_SOURCES] = encodeSources(sources) }
    }

    suspend fun setStations(stations: List<Station>) {
        context.dataStore.edit { it[KEY_STATIONS] = M3uCodec.build(stations) }
    }

    suspend fun setLastStationId(id: String) {
        context.dataStore.edit { it[KEY_LAST_STATION] = id }
    }

    suspend fun feedsNow(): List<String> = decodeFeeds(context.dataStore.data.first()[KEY_FEEDS])

    suspend fun backendUrlNow(): String =
        context.dataStore.data
            .first()[KEY_BACKEND]
            .orEmpty()

    suspend fun headlinesModeNow(): Boolean = context.dataStore.data.first()[KEY_HEADLINES] ?: false

    suspend fun topSourcesNow(): Set<String> = decodeSources(context.dataStore.data.first()[KEY_TOP_SOURCES])

    suspend fun stationsNow(): List<Station> =
        M3uCodec.parse(
            context.dataStore.data
                .first()[KEY_STATIONS]
                .orEmpty(),
        )

    suspend fun lastStationIdNow(): String? = context.dataStore.data.first()[KEY_LAST_STATION]

    /** Blocking reads for the widget factory / provider (already off the main thread). */
    fun feedsBlocking(): List<String> = runBlocking { feedsNow() }

    fun backendUrlBlocking(): String = runBlocking { backendUrlNow() }

    fun headlinesModeBlocking(): Boolean = runBlocking { headlinesModeNow() }

    fun topSourcesBlocking(): Set<String> = runBlocking { topSourcesNow() }

    fun stationsBlocking(): List<Station> = runBlocking { stationsNow() }

    fun lastStationIdBlocking(): String? = runBlocking { lastStationIdNow() }

    private fun decodeFeeds(raw: String?): List<String> {
        val urls = raw?.split(",")?.map { it.trim() }?.filter { it.isNotEmpty() } ?: emptyList()
        return urls.ifEmpty { NewsRepository.DEFAULT_FEEDS }
    }

    private fun decodeSources(raw: String?): Set<String> =
        raw
            ?.split("\n")
            ?.map { it.trim() }
            ?.filter { it.isNotEmpty() }
            ?.toSet() ?: emptySet()

    private fun encodeSources(sources: Set<String>): String = sources.map { it.trim() }.filter { it.isNotEmpty() }.joinToString("\n")

    companion object {
        private val KEY_FEEDS = stringPreferencesKey("feeds")
        private val KEY_BACKEND = stringPreferencesKey("backend_url")
        private val KEY_INTERVAL = intPreferencesKey("interval_seconds")
        private val KEY_HEADLINES = booleanPreferencesKey("headlines_mode")
        private val KEY_TOP_SOURCES = stringPreferencesKey("top_sources")
        private val KEY_STATIONS = stringPreferencesKey("stations")
        private val KEY_LAST_STATION = stringPreferencesKey("last_station_id")
        const val DEFAULT_INTERVAL = 7
    }
}
