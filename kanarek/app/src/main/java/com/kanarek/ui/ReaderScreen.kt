package com.kanarek.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
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
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.kanarek.R
import com.kanarek.data.FeedParser
import com.kanarek.data.Headlines
import com.kanarek.data.NewsItem
import com.kanarek.data.NewsRepository
import com.kanarek.data.Opml
import com.kanarek.data.SettingsStore
import com.kanarek.data.SiteSubscribe
import com.kanarek.widget.KanarekWidgetProvider
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** The news page has a reader, an article preview, and settings behind the gear. */
private enum class Screen { READER, ARTICLE, SETTINGS }

/**
 * The news half of the app, hosted as a page of [com.kanarek.HomeActivity]'s pager (formerly
 * the standalone MainActivity). [onMenu] opens the app-level navigation drawer.
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

    val savedFeeds by settings.feeds.collectAsStateWithLifecycle(initialValue = NewsRepository.DEFAULT_FEEDS)
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
    var screen by remember { mutableStateOf(Screen.READER) }
    var selectedArticle by remember { mutableStateOf<NewsItem?>(null) }

    val headlinesMode by settings.headlinesMode.collectAsStateWithLifecycle(initialValue = false)
    val topSources by settings.topSources.collectAsStateWithLifecycle(initialValue = emptySet())
    val perSourceCap by settings.perSourceCap.collectAsStateWithLifecycle(initialValue = 0)

    fun parseFeedField(): List<String> = effectiveText.split(",").map { it.trim() }.filter { it.isNotEmpty() }

    fun loadPreview(
        feeds: List<String>,
        backend: String,
        cap: Int = perSourceCap,
    ) {
        refreshJob?.cancel()
        val requestId = refreshRequestId + 1
        refreshRequestId = requestId
        refreshJob =
            scope.launch {
                loading = true
                val result =
                    try {
                        repository.fetch(feeds, backend, limit = 15, perSourceCap = cap)
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (_: Exception) {
                        emptyList()
                    }
                // A blocking network call may finish after cancellation. Only the newest request
                // is allowed to publish data or clear the loading indicator.
                if (requestId == refreshRequestId) {
                    preview = result
                    loading = false
                    refreshJob = null
                }
            }
    }

    fun returnToReader() {
        selectedArticle = null
        screen = Screen.READER
    }

    BackHandler(enabled = isActive && screen != Screen.READER) { returnToReader() }

    // Land on actual news: pull the stories as soon as the saved feeds/backend resolve, so the
    // reader is populated without the user having to hit refresh. Re-runs if the saved settings
    // change (e.g. after editing feeds on the settings screen).
    LaunchedEffect(savedFeeds, savedBackend) {
        loadPreview(savedFeeds, savedBackend)
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
        val opened = runCatching {
            context.startActivity(Intent(Intent.ACTION_VIEW, uri))
            true
        }.getOrDefault(false)
        if (!opened) Toast.makeText(context, openFailedMsg, Toast.LENGTH_SHORT).show()
    }

    // Append one feed URL (native or a Worker /scrape URL) to the list, de-duped,
    // then persist and refresh the widget — same path as OPML import.
    fun addFeedUrl(url: String) {
        val merged = (parseFeedField() + url).distinct()
        feedText = merged.joinToString(",\n")
        scope.launch {
            settings.setFeeds(merged.joinToString(","))
            KanarekWidgetProvider.refreshAll(context)
            loadPreview(merged, savedBackend)
        }
    }

    // Pick an OPML file and merge its feeds into the current list (order-preserving, de-duped).
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

    // Write the current feed list out as an OPML file the user names.
    val exportLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/x-opml")) { uri ->
            uri ?: return@rememberLauncherForActivityResult
            val feeds = parseFeedField().ifEmpty { NewsRepository.DEFAULT_FEEDS }
            scope.launch {
                withContext(Dispatchers.IO) {
                    runCatching {
                        context.contentResolver.openOutputStream(uri)?.use { it.write(Opml.build(feeds).toByteArray()) }
                    }
                }
            }
        }

    val shown =
        remember(preview, headlinesMode, topSources) {
            if (headlinesMode) Headlines.headlines(preview, topSources = topSources, limit = 15) else preview
        }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        stringResource(
                            when (screen) {
                                Screen.READER -> R.string.home_news
                                Screen.ARTICLE -> R.string.article_preview
                                Screen.SETTINGS -> R.string.settings
                            },
                        ),
                    )
                },
                navigationIcon = {
                    if (screen != Screen.READER) {
                        IconButton(onClick = { returnToReader() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.close))
                        }
                    } else {
                        IconButton(onClick = onMenu) {
                            Icon(Icons.Filled.Menu, contentDescription = stringResource(R.string.menu))
                        }
                    }
                },
                actions = {
                    if (screen == Screen.READER) {
                        IconButton(onClick = { loadPreview(savedFeeds, savedBackend) }) {
                            Icon(Icons.Filled.Refresh, contentDescription = stringResource(R.string.refresh_preview))
                        }
                        IconButton(onClick = { screen = Screen.SETTINGS }) {
                            Icon(Icons.Filled.Settings, contentDescription = stringResource(R.string.settings))
                        }
                    }
                },
            )
        },
    ) { padding ->
        when (screen) {
            Screen.READER -> {
                Box(
                    modifier =
                        Modifier
                            .fillMaxSize()
                            .padding(padding),
                    contentAlignment = Alignment.Center,
                ) {
                    when {
                        loading && shown.isEmpty() -> CircularProgressIndicator()
                        shown.isEmpty() ->
                            Text(
                                stringResource(R.string.reader_empty),
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.padding(24.dp),
                            )
                        else ->
                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                items(shown) { item ->
                                    PreviewCard(
                                        item = item,
                                        onClick = {
                                            selectedArticle = item
                                            screen = Screen.ARTICLE
                                        },
                                    )
                                }
                            }
                    }
                }
            }

            Screen.ARTICLE -> {
                selectedArticle?.let { item ->
                    ArticlePreview(
                        item = item,
                        onOpenArticle = { openArticleExternally(item.link) },
                        modifier =
                            Modifier
                                .fillMaxSize()
                                .padding(padding),
                    )
                }
            }

            Screen.SETTINGS -> {
                Column(
                    modifier =
                        Modifier
                            .fillMaxSize()
                            .padding(padding)
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(
                        stringResource(R.string.feeds_label),
                        style = MaterialTheme.typography.labelLarge,
                    )
                    OutlinedTextField(
                        value = effectiveText,
                        onValueChange = { feedText = it },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        maxLines = 6,
                    )

                    Text(
                        stringResource(R.string.backend_label),
                        style = MaterialTheme.typography.labelLarge,
                    )
                    OutlinedTextField(
                        value = effectiveBackend,
                        onValueChange = { backendText = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        placeholder = { Text(stringResource(R.string.backend_hint)) },
                    )

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = {
                            val feeds = parseFeedField()
                            val backend = effectiveBackend.trim()
                            scope.launch {
                                settings.setFeeds(feeds.joinToString(","))
                                settings.setBackendUrl(backend)
                                KanarekWidgetProvider.refreshAll(context)
                                loadPreview(feeds.ifEmpty { NewsRepository.DEFAULT_FEEDS }, backend)
                                Toast.makeText(context, savedMsg, Toast.LENGTH_SHORT).show()
                            }
                        }) { Text(stringResource(R.string.save_update_widget)) }
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = {
                            importLauncher.launch(arrayOf("text/x-opml", "application/xml", "text/xml", "*/*"))
                        }) { Text(stringResource(R.string.import_opml)) }
                        OutlinedButton(onClick = { exportLauncher.launch("kanarek-feeds.opml") }) {
                            Text(stringResource(R.string.export_opml))
                        }
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { showAddSite = true }) { Text(stringResource(R.string.add_site)) }
                    }

                    Text(
                        stringResource(R.string.widget_hint),
                        style = MaterialTheme.typography.bodySmall,
                    )

                    Spacer(Modifier.height(4.dp))

                    // Headlines: when on, the reader/widget narrows to the hottest stories
                    // (ranked by recency, image, top-source weight, and cross-source corroboration).
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Switch(
                            checked = headlinesMode,
                            onCheckedChange = { scope.launch { settings.setHeadlinesMode(it) } },
                        )
                        Text(stringResource(R.string.headlines_only), style = MaterialTheme.typography.bodyMedium)
                    }

                    // Per-source cap: keep at most N stories from any single feed in the merged
                    // list, so a high-volume wire (e.g. PAP) can't swamp a recency-sorted widget.
                    Text(stringResource(R.string.per_source_cap), style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(0, 2, 3, 5).forEach { v ->
                            FilterChip(
                                selected = perSourceCap == v,
                                onClick = {
                                    scope.launch {
                                        settings.setPerSourceCap(v)
                                        KanarekWidgetProvider.refreshAll(context)
                                        loadPreview(parseFeedField().ifEmpty { NewsRepository.DEFAULT_FEEDS }, effectiveBackend.trim(), cap = v)
                                    }
                                },
                                label = { Text(if (v == 0) stringResource(R.string.cap_off) else v.toString()) },
                            )
                        }
                    }

                    val sources =
                        remember(preview) {
                            preview
                                .map { it.source }
                                .filter { it.isNotBlank() }
                                .distinct()
                                .sorted()
                        }
                    if (sources.isNotEmpty()) {
                        Text(stringResource(R.string.top_sources), style = MaterialTheme.typography.labelLarge)
                        Row(
                            modifier = Modifier.horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            sources.forEach { s ->
                                val selected = topSources.any { it.equals(s, ignoreCase = true) }
                                FilterChip(
                                    selected = selected,
                                    onClick = {
                                        val next = topSources.toMutableSet()
                                        if (selected) next.removeAll { it.equals(s, ignoreCase = true) } else next.add(s)
                                        scope.launch { settings.setTopSources(next) }
                                    },
                                    label = { Text(s) },
                                )
                            }
                        }
                    }

                    Spacer(Modifier.height(8.dp))
                }
            }
        }

        if (showAddSite) {
            AddSiteDialog(
                backend = effectiveBackend.trim().ifBlank { NewsRepository.DEFAULT_BACKEND },
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

@Composable
private fun ArticlePreview(
    item: NewsItem,
    onOpenArticle: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val metadata =
        listOf(item.source, FeedParser.relativeTime(item.publishedAtMillis))
            .filter { it.isNotBlank() }
            .joinToString(" \u00b7 ")
    val host =
        remember(item.link) {
            runCatching { Uri.parse(item.link).host?.removePrefix("www.") }.getOrNull().orEmpty()
        }

    LazyColumn(
        modifier = modifier,
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        if (!item.imageUrl.isNullOrBlank()) {
            item {
                AsyncImage(
                    model = item.imageUrl,
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
                item.title,
                style = MaterialTheme.typography.headlineSmall,
            )
        }
        item {
            Text(
                item.summary.ifBlank { stringResource(R.string.article_summary_missing) },
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
            Button(
                onClick = onOpenArticle,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.open_full_article))
            }
        }
    }
}

@Composable
private fun PreviewCard(
    item: NewsItem,
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
                Text(
                    item.title,
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
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
            }
        }
    }
}

/**
 * Leading visual for a story: the feed-supplied [imageUrl] when present, otherwise the
 * source site's favicon from a CDN (derived from [link]'s host), falling back to an RSS
 * glyph when neither loads. A small rounded box so the row layout stays stable.
 */
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
        // When there's no model, or it fails to load, fall back to the RSS glyph.
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
private fun AddSiteDialog(
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
        val s = site.trim()
        return if (s.startsWith("http://") || s.startsWith("https://")) s else "https://$s"
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
                                runCatching { SiteSubscribe.discover(backend, url) }.getOrDefault(emptyList())
                            }
                        discovered = found
                        searched = true
                        busy = false
                        status = if (found.isEmpty()) noneMsg else foundFmt.format(found.size)
                    }
                },
            ) { Text(stringResource(R.string.find_feed)) }
        },
        dismissButton = { TextButton(enabled = !busy, onClick = onDismiss) { Text(stringResource(R.string.close)) } },
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

                discovered.forEach { d ->
                    Card(
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .clickable { onAdd(d.url) },
                    ) {
                        Column(Modifier.padding(10.dp)) {
                            Text(
                                d.title.ifBlank { d.url },
                                style = MaterialTheme.typography.titleSmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                d.url,
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
                                        runCatching { repository.fetch(listOf(scrape), backend, limit = 5) }
                                            .getOrDefault(emptyList())
                                    }
                                busy = false
                                if (items.isNotEmpty()) {
                                    onAdd(scrape)
                                } else {
                                    status = scrapeFailedMsg
                                }
                            }
                        },
                    ) { Text(stringResource(R.string.scrape_page)) }
                }
            }
        },
    )
}
