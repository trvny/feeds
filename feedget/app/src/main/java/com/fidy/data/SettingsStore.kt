package com.fidy.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
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
class SettingsStore(private val context: Context) {

    val feeds: Flow<List<String>> = context.dataStore.data.map { prefs ->
        decodeFeeds(prefs[KEY_FEEDS])
    }

    /** Optional Cloudflare Worker base URL. Blank → parse feeds on-device. */
    val backendUrl: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_BACKEND].orEmpty()
    }

    val intervalSeconds: Flow<Int> = context.dataStore.data.map { prefs ->
        prefs[KEY_INTERVAL] ?: DEFAULT_INTERVAL
    }

    suspend fun setFeeds(raw: String) {
        context.dataStore.edit { it[KEY_FEEDS] = raw.trim() }
    }

    suspend fun setBackendUrl(url: String) {
        context.dataStore.edit { it[KEY_BACKEND] = url.trim() }
    }

    suspend fun setIntervalSeconds(seconds: Int) {
        context.dataStore.edit { it[KEY_INTERVAL] = seconds.coerceIn(3, 120) }
    }

    suspend fun feedsNow(): List<String> = decodeFeeds(context.dataStore.data.first()[KEY_FEEDS])

    suspend fun backendUrlNow(): String = context.dataStore.data.first()[KEY_BACKEND].orEmpty()

    /** Blocking reads for the widget factory (already off the main thread). */
    fun feedsBlocking(): List<String> = runBlocking { feedsNow() }
    fun backendUrlBlocking(): String = runBlocking { backendUrlNow() }

    private fun decodeFeeds(raw: String?): List<String> {
        val urls = raw?.split(",")?.map { it.trim() }?.filter { it.isNotEmpty() } ?: emptyList()
        return urls.ifEmpty { NewsRepository.DEFAULT_FEEDS }
    }

    companion object {
        private val KEY_FEEDS = stringPreferencesKey("feeds")
        private val KEY_BACKEND = stringPreferencesKey("backend_url")
        private val KEY_INTERVAL = intPreferencesKey("interval_seconds")
        const val DEFAULT_INTERVAL = 7
    }
}
