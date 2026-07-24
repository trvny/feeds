package com.kanarek.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.newsNotificationDataStore: DataStore<Preferences> by
    preferencesDataStore(name = "news_notifications")

internal data class NewsNotificationStoreState(
    val config: NewsNotificationConfig,
    val initialized: Boolean,
    val knownIds: Set<String>,
)

class NewsNotificationStore(
    private val context: Context,
) {
    val config: Flow<NewsNotificationConfig> =
        context.newsNotificationDataStore.data.map(::decodeConfig)

    suspend fun configNow(): NewsNotificationConfig =
        decodeConfig(context.newsNotificationDataStore.data.first())

    suspend fun setConfig(value: NewsNotificationConfig) {
        val normalized = value.normalized()
        context.newsNotificationDataStore.edit { prefs ->
            val previous = decodeConfig(prefs)
            writeConfig(prefs, normalized)

            val sourceSetChanged = previous.selectedFeeds != normalized.selectedFeeds
            if (!normalized.enabled || !previous.enabled || sourceSetChanged) {
                prefs.remove(KEY_INITIALIZED)
                prefs.remove(KEY_KNOWN_IDS)
            }
        }
    }

    internal suspend fun snapshotState(): NewsNotificationStoreState {
        val prefs = context.newsNotificationDataStore.data.first()
        return NewsNotificationStoreState(
            config = decodeConfig(prefs),
            initialized = prefs[KEY_INITIALIZED] ?: false,
            knownIds = prefs[KEY_KNOWN_IDS].orEmpty(),
        )
    }

    internal suspend fun replacePortableConfig(value: NewsNotificationConfig) {
        context.newsNotificationDataStore.edit { prefs ->
            writeConfig(prefs, value.normalized())
            prefs.remove(KEY_INITIALIZED)
            prefs.remove(KEY_KNOWN_IDS)
        }
    }

    internal suspend fun restoreState(state: NewsNotificationStoreState) {
        context.newsNotificationDataStore.edit { prefs ->
            writeConfig(prefs, state.config.normalized())
            if (state.initialized) {
                prefs[KEY_INITIALIZED] = true
            } else {
                prefs.remove(KEY_INITIALIZED)
            }
            if (state.knownIds.isEmpty()) {
                prefs.remove(KEY_KNOWN_IDS)
            } else {
                prefs[KEY_KNOWN_IDS] = state.knownIds
            }
        }
    }

    /** Atomically aligns the saved selection with the app's current feed catalogue. */
    internal suspend fun reconcileConfiguredFeeds(feeds: List<String>): NewsNotificationConfig {
        lateinit var result: NewsNotificationConfig
        context.newsNotificationDataStore.edit { prefs ->
            val previous = decodeConfig(prefs)
            val reconciled = previous.reconciledWith(feeds)
            if (previous != reconciled) {
                writeConfig(prefs, reconciled)
                if (previous.selectedFeeds != reconciled.selectedFeeds) {
                    prefs.remove(KEY_INITIALIZED)
                    prefs.remove(KEY_KNOWN_IDS)
                }
            }
            result = reconciled
        }
        return result
    }

    /**
     * Atomically records one fetch only if its configuration is still current. A source change
     * during a slow request cannot seed or notify from the old selection.
     */
    internal suspend fun recordFetch(
        expectedConfig: NewsNotificationConfig,
        items: List<NewsItem>,
        minuteOfDay: Int,
    ): NewsNotificationDecision? {
        var result: NewsNotificationDecision? = null
        val expected = expectedConfig.normalized()
        context.newsNotificationDataStore.edit { prefs ->
            val current = decodeConfig(prefs)
            if (!current.enabled || current != expected) return@edit
            val decision =
                NewsNotifications.evaluate(
                    NewsNotificationSnapshot(
                        currentItems = items,
                        knownIds = prefs[KEY_KNOWN_IDS].orEmpty(),
                        initialized = prefs[KEY_INITIALIZED] ?: false,
                        minuteOfDay = minuteOfDay,
                        config = current,
                    ),
                )
            prefs[KEY_KNOWN_IDS] = decision.knownIds
            prefs[KEY_INITIALIZED] = true
            result = decision
        }
        return result
    }

    private companion object {
        val KEY_ENABLED = booleanPreferencesKey("enabled")
        val KEY_FEEDS = stringPreferencesKey("feeds")
        val KEY_CONFIGURED_FEEDS = stringPreferencesKey("configured_feeds")
        val KEY_QUIET_ENABLED = booleanPreferencesKey("quiet_enabled")
        val KEY_QUIET_START = intPreferencesKey("quiet_start_minute")
        val KEY_QUIET_END = intPreferencesKey("quiet_end_minute")
        val KEY_INITIALIZED = booleanPreferencesKey("initialized")
        val KEY_KNOWN_IDS = stringSetPreferencesKey("known_article_ids")

        fun decodeConfig(prefs: Preferences): NewsNotificationConfig =
            NewsNotificationConfig(
                enabled = prefs[KEY_ENABLED] ?: false,
                selectedFeeds = decodeFeeds(prefs[KEY_FEEDS]),
                configuredFeeds = decodeFeeds(prefs[KEY_CONFIGURED_FEEDS]),
                quietHoursEnabled = prefs[KEY_QUIET_ENABLED] ?: true,
                quietStartMinute =
                    prefs[KEY_QUIET_START]
                        ?: NewsNotificationConfig.DEFAULT_QUIET_START_MINUTE,
                quietEndMinute =
                    prefs[KEY_QUIET_END]
                        ?: NewsNotificationConfig.DEFAULT_QUIET_END_MINUTE,
            ).normalized()

        fun writeConfig(
            prefs: MutablePreferences,
            config: NewsNotificationConfig,
        ) {
            prefs[KEY_ENABLED] = config.enabled
            prefs[KEY_FEEDS] = encodeFeeds(config.selectedFeeds)
            prefs[KEY_CONFIGURED_FEEDS] = encodeFeeds(config.configuredFeeds)
            prefs[KEY_QUIET_ENABLED] = config.quietHoursEnabled
            prefs[KEY_QUIET_START] = config.quietStartMinute
            prefs[KEY_QUIET_END] = config.quietEndMinute
        }

        fun encodeFeeds(feeds: List<String>): String = feeds.joinToString("\n")

        fun decodeFeeds(raw: String?): List<String> =
            raw
                .orEmpty()
                .lineSequence()
                .map(String::trim)
                .filter(String::isNotEmpty)
                .distinct()
                .toList()
    }
}
