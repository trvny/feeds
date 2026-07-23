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
                savedArticles = SavedArticleCodec.decodeAll(prefs[KEY_SAVED].orEmpty()),
                hiddenIds =
                    ArticleIdHistory.ids(
                        ArticleIdHistory.prune(
                            records = prefs[KEY_HIDDEN].orEmpty(),
                            nowMillis = now,
                            maxAgeMillis = HIDDEN_MAX_AGE_MILLIS,
                            maxCount = MAX_HISTORY_ITEMS,
                        ),
                    ),
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
            pruneHistories(prefs, nowMillis())
            val records = prefs[KEY_SAVED].orEmpty().toMutableSet()
            val matching = records.filter { SavedArticleCodec.decode(it)?.let(ArticleStates::id) == id }
            if (matching.isEmpty()) {
                records += SavedArticleCodec.encode(item)
            } else {
                records -= matching.toSet()
            }
            prefs[KEY_SAVED] = records
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
            prefs[KEY_SAVED] =
                prefs[KEY_SAVED].orEmpty().filterTo(mutableSetOf()) {
                    SavedArticleCodec.decode(it)?.let(ArticleStates::id) != id
                }
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

    companion object {
        private const val DAY_MILLIS = 24L * 60L * 60L * 1000L
        private const val READ_MAX_AGE_MILLIS = 90L * DAY_MILLIS
        private const val HIDDEN_MAX_AGE_MILLIS = 180L * DAY_MILLIS
        private const val MAX_HISTORY_ITEMS = 2_000

        private val KEY_READ = stringSetPreferencesKey("read_article_ids")
        private val KEY_SAVED = stringSetPreferencesKey("saved_articles")
        private val KEY_HIDDEN = stringSetPreferencesKey("hidden_article_ids")
    }
}
