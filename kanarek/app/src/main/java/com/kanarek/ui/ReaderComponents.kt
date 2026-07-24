package com.kanarek.ui

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.BookmarkBorder
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.kanarek.R
import com.kanarek.data.ArticleListFilter
import com.kanarek.data.ArticleReader
import com.kanarek.data.ArticleState
import com.kanarek.data.ArticleStates
import com.kanarek.data.CleanArticle
import com.kanarek.data.FeedParser
import com.kanarek.data.NewsItem
import com.kanarek.data.NewsRepository
import com.kanarek.data.OfflineArticleContent
import com.kanarek.data.SiteSubscribe
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ReaderTopBar(
    route: ReaderRoute,
    onBack: () -> Unit,
    onMenu: () -> Unit,
    onRefresh: () -> Unit,
    onSettings: () -> Unit,
) {
    TopAppBar(
        title = {
            Text(
                stringResource(
                    when (route) {
                        ReaderRoute.READER -> R.string.home_news
                        ReaderRoute.ARTICLE -> R.string.article_preview
                        ReaderRoute.SETTINGS -> R.string.settings
                        ReaderRoute.STORAGE -> R.string.storage_and_data
                        ReaderRoute.NOTIFICATIONS -> R.string.news_notifications
                    },
                ),
            )
        },
        navigationIcon = {
            if (route != ReaderRoute.READER) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = stringResource(R.string.close),
                    )
                }
            } else {
                IconButton(onClick = onMenu) {
                    Icon(Icons.Filled.Menu, contentDescription = stringResource(R.string.menu))
                }
            }
        },
        actions = {
            if (route == ReaderRoute.READER) {
                IconButton(onClick = onRefresh) {
                    Icon(
                        Icons.Filled.Refresh,
                        contentDescription = stringResource(R.string.refresh_preview),
                    )
                }
                IconButton(onClick = onSettings) {
                    Icon(
                        Icons.Filled.Settings,
                        contentDescription = stringResource(R.string.settings),
                    )
                }
            }
        },
    )
}

@Composable
internal fun ReaderListPane(
    items: List<NewsItem>,
    loading: Boolean,
    filters: ReaderFilterState,
    sourceOptions: List<String>,
    articleState: ArticleState,
    onFiltersChange: (ReaderFilterState) -> Unit,
    onOpenArticle: (NewsItem) -> Unit,
    onToggleSaved: (NewsItem) -> Unit,
    onHide: (NewsItem) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier) {
        ArticleFilterControls(
            selected = filters.filter,
            onSelected = { onFiltersChange(filters.copy(filter = it)) },
            searchQuery = filters.query,
            onSearchQueryChanged = { onFiltersChange(filters.copy(query = it)) },
            sourceOptions = sourceOptions,
            selectedSources = filters.sources,
            onToggleSource = { onFiltersChange(filters.toggleSource(it)) },
            onClearSources = { onFiltersChange(filters.copy(sources = emptySet())) },
        )
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .weight(1f),
            contentAlignment = Alignment.Center,
        ) {
            when {
                loading &&
                    items.isEmpty() &&
                    filters.filter != ArticleListFilter.SAVED &&
                    !filters.hasSearchFilters -> {
                    CircularProgressIndicator()
                }

                items.isEmpty() -> {
                    Text(
                        if (filters.hasSearchFilters) {
                            stringResource(R.string.reader_empty_search)
                        } else {
                            stringResource(
                                when (filters.filter) {
                                    ArticleListFilter.ALL -> R.string.reader_empty
                                    ArticleListFilter.UNREAD -> R.string.reader_empty_unread
                                    ArticleListFilter.SAVED -> R.string.reader_empty_saved
                                },
                            )
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(24.dp),
                    )
                }

                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(
                            items = items,
                            key = { ArticleStates.id(it) },
                        ) { item ->
                            SwipeArticleCard(
                                item = item,
                                isRead = articleState.isRead(item),
                                isSaved = articleState.isSaved(item),
                                hasOfflineArticle = articleState.offlineArticle(item) != null,
                                onClick = { onOpenArticle(item) },
                                onToggleSaved = { onToggleSaved(item) },
                                onHide = { onHide(item) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
internal fun ReaderSettingsPane(
    state: ReaderSettingsUiState,
    actions: ReaderSettingsActions,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier =
            modifier
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            stringResource(R.string.feeds_label),
            style = MaterialTheme.typography.labelLarge,
        )
        OutlinedTextField(
            value = state.feedText,
            onValueChange = actions.onFeedTextChange,
            modifier = Modifier.fillMaxWidth(),
            minLines = 3,
            maxLines = 6,
        )

        Text(
            stringResource(R.string.backend_label),
            style = MaterialTheme.typography.labelLarge,
        )
        OutlinedTextField(
            value = state.backendText,
            onValueChange = actions.onBackendTextChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            placeholder = { Text(stringResource(R.string.backend_hint)) },
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = actions.onSave) {
                Text(stringResource(R.string.save_update_widget))
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = actions.onImportOpml) {
                Text(stringResource(R.string.import_opml))
            }
            OutlinedButton(onClick = actions.onExportOpml) {
                Text(stringResource(R.string.export_opml))
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = actions.onAddSite) {
                Text(stringResource(R.string.add_site))
            }
        }

        OutlinedButton(
            onClick = actions.onOpenStorage,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.storage_and_data))
        }

        OutlinedButton(
            onClick = actions.onOpenNotifications,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.news_notifications))
        }

        Text(
            stringResource(R.string.widget_hint),
            style = MaterialTheme.typography.bodySmall,
        )

        Text(
            stringResource(R.string.widget_interval),
            style = MaterialTheme.typography.labelLarge,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(5, 7, 10, 15, 30).forEach { seconds ->
                FilterChip(
                    selected = state.intervalSeconds == seconds,
                    onClick = { actions.onIntervalChange(seconds) },
                    label = {
                        Text(stringResource(R.string.widget_interval_seconds, seconds))
                    },
                )
            }
        }

        androidx.compose.foundation.layout.Spacer(Modifier.height(4.dp))

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Switch(
                checked = state.headlinesMode,
                onCheckedChange = actions.onHeadlinesChange,
            )
            Text(
                stringResource(R.string.headlines_only),
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        Text(
            stringResource(R.string.per_source_cap),
            style = MaterialTheme.typography.labelLarge,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(0, 2, 3, 5).forEach { value ->
                FilterChip(
                    selected = state.perSourceCap == value,
                    onClick = { actions.onPerSourceCapChange(value) },
                    label = {
                        Text(
                            if (value == 0) {
                                stringResource(R.string.cap_off)
                            } else {
                                value.toString()
                            },
                        )
                    },
                )
            }
        }

        if (state.previewSources.isNotEmpty()) {
            Text(
                stringResource(R.string.top_sources),
                style = MaterialTheme.typography.labelLarge,
            )
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                state.previewSources.forEach { source ->
                    FilterChip(
                        selected = state.topSources.any { it.equals(source, ignoreCase = true) },
                        onClick = { actions.onToggleTopSource(source) },
                        label = { Text(source) },
                    )
                }
            }
        }

        androidx.compose.foundation.layout.Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun ArticleFilterControls(
    selected: ArticleListFilter,
    onSelected: (ArticleListFilter) -> Unit,
    searchQuery: String,
    onSearchQueryChanged: (String) -> Unit,
    sourceOptions: List<String>,
    selectedSources: Set<String>,
    onToggleSource: (String) -> Unit,
    onClearSources: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
    ) {
        OutlinedTextField(
            value = searchQuery,
            onValueChange = onSearchQueryChanged,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            singleLine = true,
            label = { Text(stringResource(R.string.search_articles)) },
            leadingIcon = {
                Icon(Icons.Filled.Search, contentDescription = null)
            },
            trailingIcon = {
                if (searchQuery.isNotEmpty()) {
                    IconButton(onClick = { onSearchQueryChanged("") }) {
                        Icon(
                            Icons.Filled.Clear,
                            contentDescription = stringResource(R.string.clear_search),
                        )
                    }
                }
            },
        )
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ArticleListFilter.entries.forEach { filter ->
                FilterChip(
                    selected = selected == filter,
                    onClick = { onSelected(filter) },
                    label = {
                        Text(
                            stringResource(
                                when (filter) {
                                    ArticleListFilter.ALL -> R.string.filter_all
                                    ArticleListFilter.UNREAD -> R.string.filter_unread
                                    ArticleListFilter.SAVED -> R.string.filter_saved_articles
                                },
                            ),
                        )
                    },
                )
            }
        }
        if (sourceOptions.isNotEmpty()) {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = selectedSources.isEmpty(),
                    onClick = onClearSources,
                    label = { Text(stringResource(R.string.filter_all_sources)) },
                )
                sourceOptions.forEach { source ->
                    FilterChip(
                        selected = selectedSources.any {
                            it.equals(source, ignoreCase = true)
                        },
                        onClick = { onToggleSource(source) },
                        label = { Text(source) },
                    )
                }
            }
        }
    }
}

@Composable
internal fun ArticlePreview(
    item: NewsItem,
    backendUrl: String,
    reader: ArticleReader,
    isSaved: Boolean,
    offlineArticle: OfflineArticleContent?,
    onToggleSaved: (CleanArticle?) -> Unit,
    onCleanArticleLoaded: (CleanArticle) -> Unit,
    onOpenArticle: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val cleanReaderEnabled = backendUrl.isNotBlank()
    val storedArticle = offlineArticle?.asCleanArticle()
    val currentOnCleanArticleLoaded by rememberUpdatedState(onCleanArticleLoaded)
    var cleanArticle by
        remember(item.link, backendUrl, offlineArticle) {
            mutableStateOf(storedArticle)
        }
    var cleanLoading by
        remember(item.link, backendUrl, offlineArticle) {
            mutableStateOf(storedArticle == null && cleanReaderEnabled)
        }
    var cleanAttempted by
        remember(item.link, backendUrl, offlineArticle) {
            mutableStateOf(storedArticle != null)
        }

    LaunchedEffect(item.link, backendUrl, offlineArticle) {
        cleanArticle = storedArticle
        cleanAttempted = storedArticle != null
        if (storedArticle != null) {
            cleanLoading = false
            return@LaunchedEffect
        }
        if (!cleanReaderEnabled) {
            cleanLoading = false
            return@LaunchedEffect
        }
        cleanLoading = true
        cleanArticle =
            try {
                reader.fetch(item.link, backendUrl)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                null
            }
        cleanArticle?.let(currentOnCleanArticleLoaded)
        cleanLoading = false
        cleanAttempted = true
    }

    val metadata =
        listOf(
            item.source,
            cleanArticle?.author.orEmpty(),
            FeedParser.relativeTime(item.publishedAtMillis),
        ).filter { it.isNotBlank() }
            .distinct()
            .joinToString(" \u00b7 ")
    val host =
        remember(item.link) {
            runCatching { Uri.parse(item.link).host?.removePrefix("www.") }
                .getOrNull()
                .orEmpty()
        }
    val imageUrl = cleanArticle?.imageUrl ?: item.imageUrl
    val body =
        cleanArticle?.content
            ?: item.summary.ifBlank { stringResource(R.string.article_summary_missing) }

    LazyColumn(
        modifier = modifier,
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        if (!imageUrl.isNullOrBlank()) {
            item {
                AsyncImage(
                    model = imageUrl,
                    contentDescription = null,
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(220.dp)
                            .clip(RoundedCornerShape(16.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant),
                    contentScale = ContentScale.Crop,
                )
            }
        }
        if (metadata.isNotBlank()) {
            item {
                Text(
                    metadata,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
        item {
            Text(
                cleanArticle?.title?.takeIf { it.isNotBlank() } ?: item.title,
                style = MaterialTheme.typography.headlineSmall,
            )
        }
        when {
            offlineArticle != null -> {
                item {
                    Text(
                        stringResource(R.string.offline_article_available),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }

            cleanReaderEnabled && cleanLoading -> {
                item {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            strokeWidth = 2.dp,
                        )
                        Text(
                            stringResource(R.string.clean_reader_loading),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }

            cleanReaderEnabled && cleanArticle != null -> {
                item {
                    Text(
                        stringResource(R.string.clean_reader_active),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }

            cleanReaderEnabled && cleanAttempted -> {
                item {
                    Text(
                        stringResource(R.string.clean_reader_fallback),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        item {
            Text(
                body,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
        if (host.isNotBlank()) {
            item {
                Text(
                    host,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        item {
            OutlinedButton(
                onClick = { onToggleSaved(cleanArticle) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    stringResource(
                        if (isSaved) R.string.remove_saved_article else R.string.save_article,
                    ),
                )
            }
        }
        item {
            Button(
                onClick = onOpenArticle,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.open_full_article))
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SwipeArticleCard(
    item: NewsItem,
    isRead: Boolean,
    isSaved: Boolean,
    hasOfflineArticle: Boolean,
    onClick: () -> Unit,
    onToggleSaved: () -> Unit,
    onHide: () -> Unit,
) {
    val state =
        rememberSwipeToDismissBoxState(
            confirmValueChange = { value ->
                when (value) {
                    SwipeToDismissBoxValue.StartToEnd -> onToggleSaved()
                    SwipeToDismissBoxValue.EndToStart -> onHide()
                    SwipeToDismissBoxValue.Settled ->
                        return@rememberSwipeToDismissBoxState true
                }
                false
            },
        )

    SwipeToDismissBox(
        state = state,
        backgroundContent = {
            Row(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(horizontal = 24.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    if (isSaved) Icons.Filled.Bookmark else Icons.Filled.BookmarkBorder,
                    contentDescription =
                        stringResource(
                            if (isSaved) {
                                R.string.remove_saved_article
                            } else {
                                R.string.save_article
                            },
                        ),
                )
                Icon(
                    Icons.Filled.VisibilityOff,
                    contentDescription = stringResource(R.string.hide_article),
                )
            }
        },
        content = {
            PreviewCard(
                item = item,
                isRead = isRead,
                isSaved = isSaved,
                hasOfflineArticle = hasOfflineArticle,
                onClick = onClick,
            )
        },
    )
}

@Composable
private fun PreviewCard(
    item: NewsItem,
    isRead: Boolean,
    isSaved: Boolean,
    hasOfflineArticle: Boolean,
    onClick: () -> Unit,
) {
    Card(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Thumbnail(imageUrl = item.imageUrl, link = item.link)
            Column(Modifier.weight(1f)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        item.title,
                        style = MaterialTheme.typography.titleSmall,
                        color =
                            if (isRead) {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            } else {
                                MaterialTheme.colorScheme.onSurface
                            },
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    if (isSaved) {
                        Icon(
                            Icons.Filled.Bookmark,
                            contentDescription = stringResource(R.string.saved),
                            modifier = Modifier.size(18.dp),
                            tint = MaterialTheme.colorScheme.primary,
                        )
                    }
                    if (isRead) {
                        Icon(
                            Icons.Filled.CheckCircle,
                            contentDescription = stringResource(R.string.article_read),
                            modifier = Modifier.size(18.dp),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                if (item.summary.isNotBlank()) {
                    Text(
                        item.summary,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(
                    listOf(item.source, FeedParser.relativeTime(item.publishedAtMillis))
                        .filter { it.isNotBlank() }
                        .joinToString(" \u00b7 "),
                    style = MaterialTheme.typography.labelSmall,
                )
                if (hasOfflineArticle) {
                    Text(
                        stringResource(R.string.offline_article_available),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
    }
}

@Composable
private fun Thumbnail(
    imageUrl: String?,
    link: String,
) {
    val host =
        remember(link) {
            runCatching {
                java.net
                    .URI(link)
                    .host
                    ?.removePrefix("www.")
            }.getOrNull().orEmpty()
        }
    val isFavicon = imageUrl.isNullOrBlank()
    val model =
        when {
            !imageUrl.isNullOrBlank() -> imageUrl
            host.isNotBlank() -> "https://icons.duckduckgo.com/ip3/$host.ico"
            else -> null
        }
    val rss = painterResource(R.drawable.ic_rss_fallback)

    Box(
        modifier =
            Modifier
                .size(64.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        AsyncImage(
            model = model,
            contentDescription = null,
            error = rss,
            fallback = rss,
            modifier = if (isFavicon) Modifier.size(24.dp) else Modifier.fillMaxSize(),
            contentScale = if (isFavicon) ContentScale.Fit else ContentScale.Crop,
        )
    }
}

@Composable
internal fun AddSiteDialog(
    backend: String,
    repository: NewsRepository,
    onAdd: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val noneMsg = stringResource(R.string.add_site_none)
    val foundFmt = stringResource(R.string.add_site_found)
    val scrapingMsg = stringResource(R.string.scraping)
    val scrapeFailedMsg = stringResource(R.string.scrape_failed)
    var site by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) }
    var discovered by remember { mutableStateOf<List<SiteSubscribe.Discovered>>(emptyList()) }
    var searched by remember { mutableStateOf(false) }

    fun normalized(): String {
        val value = site.trim()
        return if (value.startsWith("http://") || value.startsWith("https://")) {
            value
        } else {
            "https://$value"
        }
    }

    AlertDialog(
        onDismissRequest = { if (!busy) onDismiss() },
        confirmButton = {
            TextButton(
                enabled = !busy && site.isNotBlank(),
                onClick = {
                    val url = normalized()
                    busy = true
                    status = null
                    discovered = emptyList()
                    searched = false
                    scope.launch {
                        val found =
                            withContext(Dispatchers.IO) {
                                runCatching {
                                    SiteSubscribe.discover(backend, url)
                                }.getOrDefault(emptyList())
                            }
                        discovered = found
                        searched = true
                        busy = false
                        status = if (found.isEmpty()) noneMsg else foundFmt.format(found.size)
                    }
                },
            ) {
                Text(stringResource(R.string.find_feed))
            }
        },
        dismissButton = {
            TextButton(enabled = !busy, onClick = onDismiss) {
                Text(stringResource(R.string.close))
            }
        },
        title = { Text(stringResource(R.string.add_site_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = site,
                    onValueChange = { site = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    placeholder = { Text(stringResource(R.string.add_site_hint)) },
                )

                if (busy) CircularProgressIndicator()
                status?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

                discovered.forEach { discoveredFeed ->
                    Card(
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .clickable { onAdd(discoveredFeed.url) },
                    ) {
                        Column(Modifier.padding(10.dp)) {
                            Text(
                                discoveredFeed.title.ifBlank { discoveredFeed.url },
                                style = MaterialTheme.typography.titleSmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                discoveredFeed.url,
                                style = MaterialTheme.typography.labelSmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                }

                if (searched && discovered.isEmpty() && !busy) {
                    OutlinedButton(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            val scrape = SiteSubscribe.scrapeUrl(backend, normalized())
                            busy = true
                            status = scrapingMsg
                            scope.launch {
                                val items =
                                    withContext(Dispatchers.IO) {
                                        runCatching {
                                            repository.fetch(
                                                listOf(scrape),
                                                backend,
                                                limit = 5,
                                            )
                                        }.getOrDefault(emptyList())
                                    }
                                busy = false
                                if (items.isNotEmpty()) {
                                    onAdd(scrape)
                                } else {
                                    status = scrapeFailedMsg
                                }
                            }
                        },
                    ) {
                        Text(stringResource(R.string.scrape_page))
                    }
                }
            }
        },
    )
}
