package com.kanarek.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kanarek.R
import com.kanarek.data.ArticleReader
import com.kanarek.data.ArticleState
import com.kanarek.data.ArticleStateStore
import com.kanarek.data.ArticleStates
import com.kanarek.data.CleanArticle
import com.kanarek.data.Headlines
import com.kanarek.data.NewsItem
import com.kanarek.data.NewsNotificationConfig
import com.kanarek.data.NewsNotificationStore
import com.kanarek.data.NewsRepository
import com.kanarek.data.Opml
import com.kanarek.data.ReaderFeedSyncConfig
import com.kanarek.data.ReaderFeedSynchronizer
import com.kanarek.data.SettingsStore
import com.kanarek.data.configuredReaderBackend
import com.kanarek.notifications.NewsNotificationWorker
import com.kanarek.reader.ReaderRefreshWorker
import com.kanarek.widget.KanarekWidgetProvider
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The news half of the app, hosted as a page of [com.kanarek.HomeActivity]'s pager. This function
 * owns effects and app stores; reusable UI and pure screen state live in ReaderComponents and
 * ReaderUiState.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ReaderScreen(
    settings: SettingsStore,
    repository: NewsRepository,
    isActive: Boolean,
    onMenu: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val context = androidx.compose.ui.platform.LocalContext.current
    val savedMsg = stringResource(R.string.saved)
    val openFailedMsg = stringResource(R.string.article_open_failed)
    val articleReader = remember { ArticleReader() }
    val articleStateStore = remember(context) { ArticleStateStore(context.applicationContext) }
    val notificationStore = remember(context) { NewsNotificationStore(context.applicationContext) }
    val feedSynchronizer =
        remember(context, repository) {
            ReaderFeedSynchronizer(context.applicationContext, repository)
        }
    val articleState by articleStateStore.state.collectAsStateWithLifecycle(initialValue = ArticleState())
    val notificationConfig by
        notificationStore.config.collectAsStateWithLifecycle(
            initialValue = NewsNotificationConfig(),
        )

    val savedFeeds by
        settings.feeds.collectAsStateWithLifecycle(
            initialValue = NewsRepository.DEFAULT_FEEDS,
        )
    val savedBackend by settings.backendUrl.collectAsStateWithLifecycle(initialValue = "")

    var feedText by remember { mutableStateOf<String?>(null) }
    var backendText by remember { mutableStateOf<String?>(null) }
    val effectiveText = feedText ?: savedFeeds.joinToString(",\n")
    val effectiveBackend = backendText ?: savedBackend

    var preview by remember { mutableStateOf<List<NewsItem>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var refreshJob by remember { mutableStateOf<Job?>(null) }
    var refreshRequestId by remember { mutableIntStateOf(0) }
    var showAddSite by remember { mutableStateOf(false) }
    var navigation by remember { mutableStateOf(ReaderNavigationState()) }
    var filters by remember { mutableStateOf(ReaderFilterState()) }

    val headlinesMode by settings.headlinesMode.collectAsStateWithLifecycle(initialValue = false)
    val offlineSavedArticles by
        settings.offlineSavedArticles.collectAsStateWithLifecycle(initialValue = false)
    val topSources by settings.topSources.collectAsStateWithLifecycle(initialValue = emptySet())
    val perSourceCap by settings.perSourceCap.collectAsStateWithLifecycle(initialValue = 0)
    val intervalSeconds by
        settings.intervalSeconds.collectAsStateWithLifecycle(
            initialValue = SettingsStore.DEFAULT_INTERVAL,
        )
    val backgroundRefreshMinutes by
        settings.backgroundRefreshMinutes.collectAsStateWithLifecycle(initialValue = 0)

    fun parseFeedField(): List<String> =
        effectiveText
            .split(",")
            .map(String::trim)
            .filter(String::isNotEmpty)

    fun loadPreview(
        feeds: List<String>,
        backend: String,
        cap: Int = perSourceCap,
    ) {
        refreshJob?.cancel()
        val requestId = refreshRequestId + 1
        refreshRequestId = requestId
        val config = ReaderFeedSyncConfig(feeds, backend, cap)
        refreshJob =
            scope.launch {
                loading = preview.isEmpty()
                val cached =
                    withContext(Dispatchers.IO) {
                        feedSynchronizer.cachedItems(config, limit = READER_ITEM_LIMIT)
                    }
                if (requestId == refreshRequestId && cached.isNotEmpty()) {
                    preview = cached
                    loading = false
                }
                val result =
                    try {
                        feedSynchronizer.refresh(config, limit = READER_ITEM_LIMIT)
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (_: Exception) {
                        null
                    }
                if (requestId == refreshRequestId) {
                    result?.let { preview = it.items }
                    loading = false
                    refreshJob = null
                }
            }
    }

    fun navigateBack() {
        navigation = navigation.back()
    }

    BackHandler(enabled = isActive && navigation.route != ReaderRoute.READER) {
        navigateBack()
    }

    LaunchedEffect(savedFeeds, savedBackend, perSourceCap) {
        loadPreview(savedFeeds, savedBackend, perSourceCap)
    }

    fun openArticleExternally(link: String) {
        val uri = runCatching { Uri.parse(link.trim()) }.getOrNull()
        val isWebLink =
            uri != null &&
                uri.scheme?.lowercase() in setOf("http", "https") &&
                !uri.host.isNullOrBlank()
        if (!isWebLink) {
            Toast.makeText(context, openFailedMsg, Toast.LENGTH_SHORT).show()
            return
        }
        val opened =
            runCatching {
                context.startActivity(Intent(Intent.ACTION_VIEW, uri))
                true
            }.getOrDefault(false)
        if (!opened) Toast.makeText(context, openFailedMsg, Toast.LENGTH_SHORT).show()
    }

    fun toggleSaved(
        item: NewsItem,
        cleanArticle: CleanArticle? = null,
        fetchIfMissing: Boolean = false,
    ) {
        val adding = !articleState.isSaved(item)
        val readerBackend = configuredReaderBackend(savedBackend)
        scope.launch {
            articleStateStore.toggleSaved(item)
            if (!adding || !offlineSavedArticles) return@launch
            val offlineArticle =
                cleanArticle
                    ?: if (fetchIfMissing && readerBackend != null) {
                        try {
                            articleReader.fetch(item.link, readerBackend)
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (_: Exception) {
                            null
                        }
                    } else {
                        null
                    }
            if (offlineArticle != null && settings.offlineSavedArticlesNow()) {
                articleStateStore.saveOffline(item, offlineArticle)
            }
        }
    }

    fun addFeedUrl(url: String) {
        val merged = (parseFeedField() + url).distinct()
        feedText = merged.joinToString(",\n")
        scope.launch {
            settings.setFeeds(merged.joinToString(","))
            KanarekWidgetProvider.refreshAll(context)
            loadPreview(merged, savedBackend)
        }
    }

    val importLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            uri ?: return@rememberLauncherForActivityResult
            scope.launch {
                val text =
                    withContext(Dispatchers.IO) {
                        runCatching {
                            context.contentResolver
                                .openInputStream(uri)
                                ?.bufferedReader()
                                ?.use { it.readText() }
                        }.getOrNull()
                    } ?: return@launch
                val merged = (parseFeedField() + Opml.parse(text)).distinct()
                if (merged.isEmpty()) return@launch
                feedText = merged.joinToString(",\n")
                settings.setFeeds(merged.joinToString(","))
                KanarekWidgetProvider.refreshAll(context)
                loadPreview(merged, savedBackend)
            }
        }

    val exportLauncher =
        rememberLauncherForActivityResult(
            ActivityResultContracts.CreateDocument("text/x-opml"),
        ) { uri ->
            uri ?: return@rememberLauncherForActivityResult
            val feeds = parseFeedField().ifEmpty { NewsRepository.DEFAULT_FEEDS }
            scope.launch {
                withContext(Dispatchers.IO) {
                    runCatching {
                        context.contentResolver.openOutputStream(uri)?.use { output ->
                            output.write(Opml.build(feeds).toByteArray())
                        }
                    }
                }
            }
        }

    val feedItems =
        remember(preview, headlinesMode, topSources) {
            if (headlinesMode) {
                Headlines.headlines(preview, topSources = topSources, limit = READER_ITEM_LIMIT)
            } else {
                preview
            }
        }
    val sourceOptions =
        remember(feedItems, articleState.savedArticles, filters.sources) {
            readerSourceOptions(
                feedItems = feedItems,
                savedArticles = articleState.savedArticles,
                selectedSources = filters.sources,
            )
        }
    val shown =
        remember(feedItems, articleState, filters) {
            ArticleStates.visible(
                feedItems = feedItems,
                state = articleState,
                filter = filters.filter,
                query = filters.query,
                sources = filters.sources,
            )
        }
    val previewSources =
        remember(preview) {
            preview
                .map(NewsItem::source)
                .filter(String::isNotBlank)
                .distinct()
                .sorted()
        }

    Scaffold(
        topBar = {
            ReaderTopBar(
                route = navigation.route,
                onBack = ::navigateBack,
                onMenu = onMenu,
                onRefresh = { loadPreview(savedFeeds, savedBackend) },
                onSettings = {
                    navigation = navigation.open(ReaderRoute.SETTINGS)
                },
            )
        },
    ) { padding ->
        when (navigation.route) {
            ReaderRoute.READER -> {
                ReaderListPane(
                    items = shown,
                    loading = loading,
                    filters = filters,
                    sourceOptions = sourceOptions,
                    articleState = articleState,
                    onFiltersChange = { filters = it },
                    onOpenArticle = { item ->
                        scope.launch { articleStateStore.markRead(item) }
                        navigation = navigation.openArticle(item)
                    },
                    onToggleSaved = { item ->
                        toggleSaved(item, fetchIfMissing = true)
                    },
                    onHide = { item ->
                        scope.launch { articleStateStore.hide(item) }
                    },
                    modifier =
                        Modifier
                            .fillMaxSize()
                            .padding(padding),
                )
            }

            ReaderRoute.ARTICLE -> {
                navigation.selectedArticle?.let { item ->
                    ArticlePreview(
                        item = item,
                        backendUrl = configuredReaderBackend(effectiveBackend).orEmpty(),
                        reader = articleReader,
                        isSaved = articleState.isSaved(item),
                        offlineArticle = articleState.offlineArticle(item),
                        onToggleSaved = { cleanArticle ->
                            toggleSaved(item, cleanArticle = cleanArticle)
                        },
                        onCleanArticleLoaded = { cleanArticle ->
                            if (offlineSavedArticles) {
                                scope.launch {
                                    articleStateStore.saveOffline(item, cleanArticle)
                                }
                            }
                        },
                        onOpenArticle = { openArticleExternally(item.link) },
                        modifier =
                            Modifier
                                .fillMaxSize()
                                .padding(padding),
                    )
                }
            }

            ReaderRoute.SETTINGS -> {
                val actions =
                    ReaderSettingsActions(
                        onFeedTextChange = { feedText = it },
                        onBackendTextChange = { backendText = it },
                        onSave = {
                            val feeds = parseFeedField()
                            val backend = effectiveBackend.trim()
                            scope.launch {
                                settings.setFeeds(feeds.joinToString(","))
                                settings.setBackendUrl(backend)
                                KanarekWidgetProvider.refreshAll(context)
                                loadPreview(
                                    feeds.ifEmpty { NewsRepository.DEFAULT_FEEDS },
                                    backend,
                                )
                                Toast.makeText(
                                    context,
                                    savedMsg,
                                    Toast.LENGTH_SHORT,
                                ).show()
                            }
                        },
                        onImportOpml = {
                            importLauncher.launch(
                                arrayOf(
                                    "text/x-opml",
                                    "application/xml",
                                    "text/xml",
                                    "*/*",
                                ),
                            )
                        },
                        onExportOpml = {
                            exportLauncher.launch("kanarek-feeds.opml")
                        },
                        onAddSite = { showAddSite = true },
                        onOpenStorage = {
                            navigation = navigation.open(ReaderRoute.STORAGE)
                        },
                        onOpenNotifications = {
                            navigation = navigation.open(ReaderRoute.NOTIFICATIONS)
                        },
                        onIntervalChange = { seconds ->
                            scope.launch {
                                settings.setIntervalSeconds(seconds)
                                KanarekWidgetProvider.updateAll(context)
                            }
                        },
                        onBackgroundRefreshChange = { minutes ->
                            scope.launch {
                                settings.setBackgroundRefreshMinutes(minutes)
                                ReaderRefreshWorker.syncSchedule(context, minutes)
                            }
                        },
                        onHeadlinesChange = { enabled ->
                            scope.launch { settings.setHeadlinesMode(enabled) }
                        },
                        onPerSourceCapChange = { value ->
                            scope.launch {
                                settings.setPerSourceCap(value)
                                KanarekWidgetProvider.refreshAll(context)
                                loadPreview(
                                    parseFeedField().ifEmpty {
                                        NewsRepository.DEFAULT_FEEDS
                                    },
                                    effectiveBackend.trim(),
                                    cap = value,
                                )
                            }
                        },
                        onToggleTopSource = { source ->
                            val selected =
                                topSources.any {
                                    it.equals(source, ignoreCase = true)
                                }
                            val next = topSources.toMutableSet()
                            if (selected) {
                                next.removeAll {
                                    it.equals(source, ignoreCase = true)
                                }
                            } else {
                                next.add(source)
                            }
                            scope.launch { settings.setTopSources(next) }
                        },
                    )
                Column(
                    modifier =
                        Modifier
                            .fillMaxSize()
                            .padding(padding),
                ) {
                    ReaderSettingsPane(
                        state =
                            ReaderSettingsUiState(
                                feedText = effectiveText,
                                backendText = effectiveBackend,
                                intervalSeconds = intervalSeconds,
                                backgroundRefreshMinutes = backgroundRefreshMinutes,
                                headlinesMode = headlinesMode,
                                perSourceCap = perSourceCap,
                                topSources = topSources,
                                previewSources = previewSources,
                            ),
                        actions = actions,
                        modifier = Modifier.weight(1f),
                    )
                    ReaderBackgroundRefreshControls(
                        selectedMinutes = backgroundRefreshMinutes,
                        onSelected = actions.onBackgroundRefreshChange,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            ReaderRoute.STORAGE -> {
                StorageScreen(
                    articleState = articleState,
                    articleStateStore = articleStateStore,
                    offlineSavedArticles = offlineSavedArticles,
                    onOfflineSavedArticlesChange = { enabled ->
                        scope.launch {
                            settings.setOfflineSavedArticles(enabled)
                        }
                    },
                    modifier = Modifier.padding(padding),
                )
            }

            ReaderRoute.NOTIFICATIONS -> {
                NewsNotificationSettingsScreen(
                    config = notificationConfig,
                    availableFeeds = savedFeeds,
                    onSave = { updated ->
                        scope.launch {
                            notificationStore.setConfig(updated)
                            NewsNotificationWorker.syncSchedule(context, updated.enabled)
                            Toast.makeText(context, savedMsg, Toast.LENGTH_SHORT).show()
                        }
                    },
                    modifier = Modifier.padding(padding),
                )
            }
        }

        if (showAddSite) {
            AddSiteDialog(
                backend =
                    effectiveBackend
                        .trim()
                        .ifBlank { NewsRepository.DEFAULT_BACKEND },
                repository = repository,
                onAdd = { url ->
                    addFeedUrl(url)
                    showAddSite = false
                },
                onDismiss = { showAddSite = false },
            )
        }
    }
}

private const val READER_ITEM_LIMIT = 15
