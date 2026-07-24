package com.kanarek.ui

import android.os.Bundle
import androidx.compose.runtime.saveable.Saver
import com.kanarek.data.ArticleListFilter
import com.kanarek.data.NewsItem

internal enum class ReaderRoute {
    READER,
    ARTICLE,
    SETTINGS,
    STORAGE,
    NOTIFICATIONS,
}

internal data class ReaderNavigationState(
    val route: ReaderRoute = ReaderRoute.READER,
    val selectedArticle: NewsItem? = null,
) {
    fun openArticle(item: NewsItem): ReaderNavigationState =
        copy(route = ReaderRoute.ARTICLE, selectedArticle = item)

    fun open(route: ReaderRoute): ReaderNavigationState =
        copy(route = route, selectedArticle = null)

    fun back(): ReaderNavigationState =
        when (route) {
            ReaderRoute.STORAGE,
            ReaderRoute.NOTIFICATIONS,
            -> copy(route = ReaderRoute.SETTINGS, selectedArticle = null)

            ReaderRoute.READER -> this
            ReaderRoute.ARTICLE,
            ReaderRoute.SETTINGS,
            -> ReaderNavigationState()
        }
}

internal data class ReaderFilterState(
    val filter: ArticleListFilter = ArticleListFilter.ALL,
    val query: String = "",
    val sources: Set<String> = emptySet(),
) {
    val hasSearchFilters: Boolean
        get() = query.isNotBlank() || sources.isNotEmpty()

    fun toggleSource(source: String): ReaderFilterState {
        val normalized = source.trim()
        if (normalized.isEmpty()) return this
        val selected = sources.any { it.equals(normalized, ignoreCase = true) }
        val next =
            if (selected) {
                sources.filterNot { it.equals(normalized, ignoreCase = true) }.toSet()
            } else {
                sources + normalized
            }
        return copy(sources = next)
    }
}

internal val ReaderNavigationStateSaver =
    Saver<ReaderNavigationState, Bundle>(
        save = { state -> state.toSavedBundle() },
        restore = ::restoreReaderNavigationState,
    )

internal val ReaderFilterStateSaver =
    Saver<ReaderFilterState, Bundle>(
        save = { state -> state.toSavedBundle() },
        restore = ::restoreReaderFilterState,
    )

internal fun ReaderNavigationState.toSavedBundle(): Bundle =
    Bundle().apply {
        putString(KEY_ROUTE, route.name)
        selectedArticle?.let { item ->
            putBoolean(KEY_HAS_ARTICLE, true)
            putString(KEY_ARTICLE_TITLE, item.title)
            putString(KEY_ARTICLE_LINK, item.link)
            putString(KEY_ARTICLE_SUMMARY, item.summary)
            putString(KEY_ARTICLE_IMAGE, item.imageUrl)
            putString(KEY_ARTICLE_SOURCE, item.source)
            item.publishedAtMillis?.let { published -> putLong(KEY_ARTICLE_PUBLISHED, published) }
        }
    }

internal fun restoreReaderNavigationState(saved: Bundle): ReaderNavigationState {
    val route = saved.enumValue(KEY_ROUTE, ReaderRoute.READER)
    val article =
        if (saved.getBoolean(KEY_HAS_ARTICLE)) {
            NewsItem(
                title = saved.getString(KEY_ARTICLE_TITLE).orEmpty(),
                link = saved.getString(KEY_ARTICLE_LINK).orEmpty(),
                summary = saved.getString(KEY_ARTICLE_SUMMARY).orEmpty(),
                imageUrl = saved.getString(KEY_ARTICLE_IMAGE),
                source = saved.getString(KEY_ARTICLE_SOURCE).orEmpty(),
                publishedAtMillis =
                    if (saved.containsKey(KEY_ARTICLE_PUBLISHED)) {
                        saved.getLong(KEY_ARTICLE_PUBLISHED)
                    } else {
                        null
                    },
            )
        } else {
            null
        }
    return if (route == ReaderRoute.ARTICLE && article == null) {
        ReaderNavigationState()
    } else {
        ReaderNavigationState(route = route, selectedArticle = article)
    }
}

internal fun ReaderFilterState.toSavedBundle(): Bundle =
    Bundle().apply {
        putString(KEY_FILTER, filter.name)
        putString(KEY_QUERY, query)
        putStringArrayList(KEY_SOURCES, ArrayList(sources))
    }

internal fun restoreReaderFilterState(saved: Bundle): ReaderFilterState =
    ReaderFilterState(
        filter = saved.enumValue(KEY_FILTER, ArticleListFilter.ALL),
        query = saved.getString(KEY_QUERY).orEmpty(),
        sources = saved.getStringArrayList(KEY_SOURCES).orEmpty().toSet(),
    )

private inline fun <reified T : Enum<T>> Bundle.enumValue(
    key: String,
    fallback: T,
): T =
    getString(key)
        ?.let { value -> enumValues<T>().firstOrNull { it.name == value } }
        ?: fallback

internal data class ReaderSettingsUiState(
    val feedText: String,
    val backendText: String,
    val intervalSeconds: Int,
    val backgroundRefreshMinutes: Int,
    val headlinesMode: Boolean,
    val perSourceCap: Int,
    val topSources: Set<String>,
    val previewSources: List<String>,
)

internal data class ReaderSettingsActions(
    val onFeedTextChange: (String) -> Unit,
    val onBackendTextChange: (String) -> Unit,
    val onSave: () -> Unit,
    val onImportOpml: () -> Unit,
    val onExportOpml: () -> Unit,
    val onAddSite: () -> Unit,
    val onOpenStorage: () -> Unit,
    val onOpenNotifications: () -> Unit,
    val onIntervalChange: (Int) -> Unit,
    val onBackgroundRefreshChange: (Int) -> Unit,
    val onHeadlinesChange: (Boolean) -> Unit,
    val onPerSourceCapChange: (Int) -> Unit,
    val onToggleTopSource: (String) -> Unit,
)

internal fun readerSourceOptions(
    feedItems: List<NewsItem>,
    savedArticles: List<NewsItem>,
    selectedSources: Set<String>,
): List<String> =
    (feedItems.map(NewsItem::source) + savedArticles.map(NewsItem::source) + selectedSources)
        .map(String::trim)
        .filter(String::isNotEmpty)
        .distinctBy { it.lowercase() }
        .sortedBy { it.lowercase() }

private const val KEY_ROUTE = "route"
private const val KEY_HAS_ARTICLE = "hasArticle"
private const val KEY_ARTICLE_TITLE = "articleTitle"
private const val KEY_ARTICLE_LINK = "articleLink"
private const val KEY_ARTICLE_SUMMARY = "articleSummary"
private const val KEY_ARTICLE_IMAGE = "articleImage"
private const val KEY_ARTICLE_SOURCE = "articleSource"
private const val KEY_ARTICLE_PUBLISHED = "articlePublished"
private const val KEY_FILTER = "filter"
private const val KEY_QUERY = "query"
private const val KEY_SOURCES = "sources"
