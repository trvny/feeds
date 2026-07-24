package com.kanarek.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.articleStateDataStore: DataStore<Preferences> by preferencesDataStore(name = "article_state")

class ArticleStateStore(
    private val context: Context,
    private val nowMillis: () -> Long = { System.currentTimeMillis() },
) {
    val state: Flow<ArticleState> =
        context.articleStateDataStore.data.map { prefs ->
            val now = nowMillis()
            val savedRecords = SavedArticleCodec.decodeRecords(prefs[KEY_SAVED].orEmpty())
            ArticleState(
                readIds =
                    ArticleIdHistory.ids(
                        ArticleIdHistory.prune(
                            records = prefs[KEY_READ].orEmpty(),
                            nowMillis = now,
                            maxAgeMillis = READ_MAX_AGE_MILLIS,
                            maxCount = MAX_HISTORY_ITEMS,
                        ),
                    ),
                savedArticles = savedRecords.map(SavedArticleRecord::item),
                hiddenIds =
                    ArticleIdHistory.ids(
                        ArticleIdHistory.prune(
                            records = prefs[KEY_HIDDEN].orEmpty(),
                            nowMillis = now,
                            maxAgeMillis = HIDDEN_MAX_AGE_MILLIS,
                            maxCount = MAX_HISTORY_ITEMS,
                        ),
                    ),
                offlineArticles =
                    savedRecords.mapNotNull { record ->
                        record.offline?.let { ArticleStates.id(record.item) to it }
                    }.toMap(),
            )
        }

    suspend fun markRead(item: NewsItem) {
        val id = ArticleStates.id(item)
        if (id.isBlank()) return
        context.articleStateDataStore.edit { prefs ->
            val now = nowMillis()
            pruneHistories(prefs, now)
            prefs[KEY_READ] =
                ArticleIdHistory.touch(
                    records = prefs[KEY_READ].orEmpty(),
                    id = id,
                    nowMillis = now,
                    maxAgeMillis = READ_MAX_AGE_MILLIS,
                    maxCount = MAX_HISTORY_ITEMS,
                )
        }
    }

    suspend fun toggleSaved(item: NewsItem) {
        val id = ArticleStates.id(item)
        if (id.isBlank()) return
        context.articleStateDataStore.edit { prefs ->
            val now = nowMillis()
            pruneHistories(prefs, now)
            val records = SavedArticleCodec.decodeRecords(prefs[KEY_SAVED].orEmpty()).toMutableList()
            val matchingIndex = records.indexOfFirst { ArticleStates.id(it.item) == id }
            if (matchingIndex < 0) {
                records +=
                    SavedArticleRecord(
                        item = item,
                        savedAtMillis = now,
                    )
            } else {
                records.removeAt(matchingIndex)
            }
            writeSavedRecords(prefs, records)
        }
    }

    /** Adds full reader text only while the bookmark still exists; a late fetch cannot restore it. */
    suspend fun saveOffline(
        item: NewsItem,
        article: CleanArticle,
    ) {
        val id = ArticleStates.id(item)
        if (id.isBlank()) return
        val now = nowMillis()
        val offline = OfflineArticles.fromCleanArticle(article, now) ?: return
        context.articleStateDataStore.edit { prefs ->
            val records = SavedArticleCodec.decodeRecords(prefs[KEY_SAVED].orEmpty()).toMutableList()
            val matchingIndex = records.indexOfFirst { ArticleStates.id(it.item) == id }
            if (matchingIndex < 0) return@edit
            records[matchingIndex] = records[matchingIndex].copy(offline = offline)
            writeSavedRecords(prefs, records)
        }
    }

    suspend fun hide(item: NewsItem) {
        val id = ArticleStates.id(item)
        if (id.isBlank()) return
        context.articleStateDataStore.edit { prefs ->
            val now = nowMillis()
            pruneHistories(prefs, now)
            prefs[KEY_HIDDEN] =
                ArticleIdHistory.touch(
                    records = prefs[KEY_HIDDEN].orEmpty(),
                    id = id,
                    nowMillis = now,
                    maxAgeMillis = HIDDEN_MAX_AGE_MILLIS,
                    maxCount = MAX_HISTORY_ITEMS,
                )
            val savedRecords =
                SavedArticleCodec.decodeRecords(prefs[KEY_SAVED].orEmpty())
                    .filterNot { ArticleStates.id(it.item) == id }
            writeSavedRecords(prefs, savedRecords)
        }
    }

    suspend fun clearReadAndHidden() {
        context.articleStateDataStore.edit { prefs ->
            prefs.remove(KEY_READ)
            prefs.remove(KEY_HIDDEN)
        }
    }

    suspend fun clearSavedArticles() {
        context.articleStateDataStore.edit { prefs ->
            prefs.remove(KEY_SAVED)
        }
    }

    private fun pruneHistories(
        prefs: MutablePreferences,
        now: Long,
    ) {
        prefs[KEY_READ] =
            ArticleIdHistory.prune(
                records = prefs[KEY_READ].orEmpty(),
                nowMillis = now,
                maxAgeMillis = READ_MAX_AGE_MILLIS,
                maxCount = MAX_HISTORY_ITEMS,
            )
        prefs[KEY_HIDDEN] =
            ArticleIdHistory.prune(
                records = prefs[KEY_HIDDEN].orEmpty(),
                nowMillis = now,
                maxAgeMillis = HIDDEN_MAX_AGE_MILLIS,
                maxCount = MAX_HISTORY_ITEMS,
            )
    }

    private fun writeSavedRecords(
        prefs: MutablePreferences,
        records: List<SavedArticleRecord>,
    ) {
        prefs[KEY_SAVED] =
            OfflineArticles
                .enforceLimit(records, OFFLINE_CONTENT_LIMIT_BYTES)
                .mapTo(mutableSetOf(), SavedArticleCodec::encodeRecord)
    }

    companion object {
        const val OFFLINE_CONTENT_LIMIT_BYTES = 2L * 1024L * 1024L

        private const val DAY_MILLIS = 24L * 60L * 60L * 1000L
        private const val READ_MAX_AGE_MILLIS = 90L * DAY_MILLIS
        private const val HIDDEN_MAX_AGE_MILLIS = 180L * DAY_MILLIS
        private const val MAX_HISTORY_ITEMS = 2_000

        private val KEY_READ = stringSetPreferencesKey("read_article_ids")
        private val KEY_SAVED = stringSetPreferencesKey("saved_articles")
        private val KEY_HIDDEN = stringSetPreferencesKey("hidden_article_ids")
    }
}
