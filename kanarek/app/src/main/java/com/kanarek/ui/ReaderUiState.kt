package com.kanarek.ui

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

internal data class ReaderSettingsUiState(
    val feedText: String,
    val backendText: String,
    val intervalSeconds: Int,
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
