package com.feedy

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.foundation.rememberScrollState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import coil.compose.AsyncImage
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.feedy.data.FeedParser
import com.feedy.data.Headlines
import com.feedy.data.NewsItem
import com.feedy.data.NewsRepository
import com.feedy.data.Opml
import com.feedy.data.SettingsStore
import com.feedy.data.SiteSubscribe
import com.feedy.ui.theme.FeedyTheme
import com.feedy.widget.FeedyWidgetProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val settings = SettingsStore(applicationContext)
        val repository = NewsRepository()
        setContent {
            FeedyTheme {
                HomeScreen(settings = settings, repository = repository)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeScreen(settings: SettingsStore, repository: NewsRepository) {
    val scope = rememberCoroutineScope()
    val context = androidx.compose.ui.platform.LocalContext.current

    val savedFeeds by settings.feeds.collectAsStateWithLifecycle(initialValue = NewsRepository.DEFAULT_FEEDS)
    val savedBackend by settings.backendUrl.collectAsStateWithLifecycle(initialValue = "")

    var feedText by remember { mutableStateOf<String?>(null) }
    var backendText by remember { mutableStateOf<String?>(null) }
    val effectiveText = feedText ?: savedFeeds.joinToString(",\n")
    val effectiveBackend = backendText ?: savedBackend

    var preview by remember { mutableStateOf<List<NewsItem>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var showAddSite by remember { mutableStateOf(false) }

    val headlinesMode by settings.headlinesMode.collectAsStateWithLifecycle(initialValue = false)
    val topSources by settings.topSources.collectAsStateWithLifecycle(initialValue = emptySet())

    fun parseFeedField(): List<String> =
        effectiveText.split(",").map { it.trim() }.filter { it.isNotEmpty() }

    fun loadPreview(feeds: List<String>, backend: String) {
        scope.launch {
            loading = true
            preview = runCatching { repository.fetch(feeds, backend, limit = 15) }.getOrDefault(emptyList())
            loading = false
        }
    }

    // Append one feed URL (native or a Worker /scrape URL) to the list, de-duped,
    // then persist and refresh the widget — same path as OPML import.
    fun addFeedUrl(url: String) {
        val merged = (parseFeedField() + url).distinct()
        feedText = merged.joinToString(",\n")
        scope.launch {
            settings.setFeeds(merged.joinToString(","))
            FeedyWidgetProvider.refreshAll(context)
            loadPreview(merged, savedBackend)
        }
    }

    // Pick an OPML file and merge its feeds into the current list (order-preserving, de-duped).
    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        scope.launch {
            val text = withContext(Dispatchers.IO) {
                runCatching {
                    context.contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() }
                }.getOrNull()
            } ?: return@launch
            val merged = (parseFeedField() + Opml.parse(text)).distinct()
            if (merged.isEmpty()) return@launch
            feedText = merged.joinToString(",\n")
            settings.setFeeds(merged.joinToString(","))
            FeedyWidgetProvider.refreshAll(context)
            loadPreview(merged, savedBackend)
        }
    }

    // Write the current feed list out as an OPML file the user names.
    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/x-opml")) { uri ->
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

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(androidx.compose.ui.res.stringResource(R.string.app_name)) },
                actions = {
                    IconButton(onClick = { loadPreview(savedFeeds, savedBackend) }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh preview")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "Feeds (comma-separated RSS or Atom URLs)",
                style = MaterialTheme.typography.labelLarge,
            )
            OutlinedTextField(
                value = effectiveText,
                onValueChange = { feedText = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
            )

            Text(
                "Backend URL (optional — deploy worker/ to a Cloudflare Worker)",
                style = MaterialTheme.typography.labelLarge,
            )
            OutlinedTextField(
                value = effectiveBackend,
                onValueChange = { backendText = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("https://feedget.<account>.workers.dev") },
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    val feeds = parseFeedField()
                    val backend = effectiveBackend.trim()
                    scope.launch {
                        settings.setFeeds(feeds.joinToString(","))
                        settings.setBackendUrl(backend)
                        FeedyWidgetProvider.refreshAll(context)
                        loadPreview(feeds.ifEmpty { NewsRepository.DEFAULT_FEEDS }, backend)
                    }
                }) { Text("Save & update widget") }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    importLauncher.launch(arrayOf("text/x-opml", "application/xml", "text/xml", "*/*"))
                }) { Text("Import OPML") }
                OutlinedButton(onClick = { exportLauncher.launch("feedy-feeds.opml") }) {
                    Text("Export OPML")
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { showAddSite = true }) { Text("Add site (no RSS needed)") }
            }

            Text(
                "Add the feedy widget from your launcher's widget picker, then drag a corner to resize it.",
                style = MaterialTheme.typography.bodySmall,
            )

            Spacer(Modifier.height(4.dp))

            // Headlines: when on, the showcase/widget narrows to the hottest stories
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

            val sources = remember(preview) {
                preview.map { it.source }.filter { it.isNotBlank() }.distinct().sorted()
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

            Text("Preview", style = MaterialTheme.typography.titleMedium)

            val shown = remember(preview, headlinesMode, topSources) {
                if (headlinesMode) Headlines.headlines(preview, topSources = topSources, limit = 15) else preview
            }
            if (loading) {
                CircularProgressIndicator()
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(shown) { item -> PreviewCard(item) }
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
}

@Composable
private fun PreviewCard(item: NewsItem) {
    Card(modifier = Modifier.fillMaxWidth()) {
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
                        .joinToString(" · "),
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
private fun Thumbnail(imageUrl: String?, link: String) {
    val host = remember(link) {
        runCatching { java.net.URI(link).host?.removePrefix("www.") }.getOrNull().orEmpty()
    }
    val isFavicon = imageUrl.isNullOrBlank()
    val model = when {
        !imageUrl.isNullOrBlank() -> imageUrl
        host.isNotBlank() -> "https://icons.duckduckgo.com/ip3/$host.ico"
        else -> null
    }
    val rss = painterResource(R.drawable.ic_rss_fallback)

    Box(
        modifier = Modifier
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
                        val found = withContext(Dispatchers.IO) {
                            runCatching { SiteSubscribe.discover(backend, url) }.getOrDefault(emptyList())
                        }
                        discovered = found
                        searched = true
                        busy = false
                        status = if (found.isEmpty()) {
                            "No native feed advertised. You can still scrape the page."
                        } else {
                            "Found ${found.size} feed(s) — tap one to add."
                        }
                    }
                },
            ) { Text("Find feed") }
        },
        dismissButton = { TextButton(enabled = !busy, onClick = onDismiss) { Text("Close") } },
        title = { Text("Add a site") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = site,
                    onValueChange = { site = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    placeholder = { Text("example.com") },
                )

                if (busy) CircularProgressIndicator()
                status?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

                discovered.forEach { d ->
                    Card(
                        modifier = Modifier
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
                            status = "Scraping the page..."
                            scope.launch {
                                val items = withContext(Dispatchers.IO) {
                                    runCatching { repository.fetch(listOf(scrape), backend, limit = 5) }
                                        .getOrDefault(emptyList())
                                }
                                busy = false
                                if (items.isNotEmpty()) {
                                    onAdd(scrape)
                                } else {
                                    status = "Couldn't extract stories from that page."
                                }
                            }
                        },
                    ) { Text("No feed? Scrape this page") }
                }
            }
        },
    )
}
