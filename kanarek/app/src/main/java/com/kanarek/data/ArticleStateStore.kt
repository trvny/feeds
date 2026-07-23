package com.kanarek.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.articleStateDataStore: DataStore<Preferences> by preferencesDataStore(name = "article_state")

class ArticleStateStore(
    private val context: Context,
) {
    val state: Flow<ArticleState> =
        context.articleStateDataStore.data.map { prefs ->
            ArticleState(
                readIds = prefs[KEY_READ].orEmpty(),
                savedArticles = SavedArticleCodec.decodeAll(prefs[KEY_SAVED].orEmpty()),
                hiddenIds = prefs[KEY_HIDDEN].orEmpty(),
            )
        }

    suspend fun markRead(item: NewsItem) {
        val id = ArticleStates.id(item)
        if (id.isBlank()) return
        context.articleStateDataStore.edit { prefs ->
            prefs[KEY_READ] = prefs[KEY_READ].orEmpty() + id
        }
    }

    suspend fun toggleSaved(item: NewsItem) {
        val id = ArticleStates.id(item)
        if (id.isBlank()) return
        context.articleStateDataStore.edit { prefs ->
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
            prefs[KEY_HIDDEN] = prefs[KEY_HIDDEN].orEmpty() + id
            prefs[KEY_SAVED] =
                prefs[KEY_SAVED].orEmpty().filterTo(mutableSetOf()) {
                    SavedArticleCodec.decode(it)?.let(ArticleStates::id) != id
                }
        }
    }

    companion object {
        private val KEY_READ = stringSetPreferencesKey("read_article_ids")
        private val KEY_SAVED = stringSetPreferencesKey("saved_articles")
        private val KEY_HIDDEN = stringSetPreferencesKey("hidden_article_ids")
    }
}
