package com.kanarek.widget

import android.content.Context

/** Per-widget configuration and a bounded last-good snapshot. */
internal class NewsWidgetStore(
    context: Context,
) {
    private val preferences =
        context.applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun config(appWidgetId: Int): NewsWidgetConfig? =
        synchronized(LOCK) {
            if (!preferences.getBoolean(key(appWidgetId, CONFIGURED), false)) {
                return@synchronized null
            }
            val feeds =
                preferences
                    .getString(key(appWidgetId, FEEDS), null)
                    .orEmpty()
                    .lineSequence()
                    .toList()
            NewsWidgetConfig(
                feeds = feeds,
                headlines = preferences.getBoolean(key(appWidgetId, HEADLINES), false),
                intervalSeconds =
                    preferences.getInt(
                        key(appWidgetId, INTERVAL),
                        com.kanarek.data.SettingsStore.DEFAULT_INTERVAL,
                    ),
            )
        }

    fun configOrMigrate(
        appWidgetId: Int,
        global: NewsWidgetConfig,
    ): NewsWidgetConfig =
        synchronized(LOCK) {
            val stored = config(appWidgetId)
            val migrated = NewsWidgetConfigs.migrate(stored, global)
            if (stored != migrated) saveConfig(appWidgetId, migrated)
            migrated
        }

    fun saveConfig(
        appWidgetId: Int,
        config: NewsWidgetConfig,
    ) {
        synchronized(LOCK) {
            val normalized = NewsWidgetConfigs.normalize(config, config.feeds)
            val previousFeeds =
                config(appWidgetId)
                    ?.let { NewsWidgetConfigs.normalize(it, normalized.feeds) }
                    ?.feeds
            preferences.edit()
                .apply {
                    if (previousFeeds != null && previousFeeds != normalized.feeds) {
                        remove(key(appWidgetId, SNAPSHOT))
                    }
                }
                .putBoolean(key(appWidgetId, CONFIGURED), true)
                .putString(key(appWidgetId, FEEDS), normalized.feeds.joinToString("\n"))
                .putBoolean(key(appWidgetId, HEADLINES), normalized.headlines)
                .putInt(key(appWidgetId, INTERVAL), normalized.intervalSeconds)
                .commit()
        }
    }

    fun snapshot(appWidgetId: Int): NewsWidgetSnapshot? =
        synchronized(LOCK) {
            NewsWidgetSnapshotCodec.decode(
                preferences.getString(key(appWidgetId, SNAPSHOT), null),
            )
        }

    fun saveSnapshot(
        appWidgetId: Int,
        snapshot: NewsWidgetSnapshot,
    ) {
        synchronized(LOCK) {
            preferences
                .edit()
                .putString(key(appWidgetId, SNAPSHOT), NewsWidgetSnapshotCodec.encode(snapshot))
                .commit()
        }
    }

    /** Commits refresh output only while its input configuration is still current. */
    fun runIfCurrent(
        appWidgetId: Int,
        expected: NewsWidgetConfig,
        action: () -> Unit,
    ): Boolean =
        synchronized(LOCK) {
            if (config(appWidgetId) != expected) return@synchronized false
            action()
            true
        }

    fun delete(appWidgetId: Int) {
        synchronized(LOCK) {
            val prefix = "$appWidgetId."
            preferences
                .edit()
                .also { editor ->
                    preferences.all.keys.filter { it.startsWith(prefix) }.forEach(editor::remove)
                }.apply()
        }
    }

    private fun key(
        appWidgetId: Int,
        suffix: String,
    ): String = "$appWidgetId.$suffix"

    companion object {
        private const val PREFERENCES_NAME = "news_widgets"
        private const val CONFIGURED = "configured"
        private const val FEEDS = "feeds"
        private const val HEADLINES = "headlines"
        private const val INTERVAL = "interval"
        private const val SNAPSHOT = "snapshot"
        private val LOCK = Any()
    }
}
