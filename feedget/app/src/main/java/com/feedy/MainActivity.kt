package com.feedy

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.feedy.data.FeedParser
import com.feedy.data.NewsItem
import com.feedy.data.NewsRepository
import com.feedy.data.Opml
import com.feedy.data.SettingsStore
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

    fun parseFeedField(): List<String> =
        effectiveText.split(",").map { it.trim() }.filter { it.isNotEmpty() }

    fun loadPreview(feeds: List<String>, backend: String) {
        scope.launch {
            loading = true
            preview = runCatching { repository.fetch(feeds, backend, limit = 15) }.getOrDefault(emptyList())
            loading = false
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
                placeholder = { Text("https://feedy-news.<account>.workers.dev") },
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

            Text(
                "Add the feedy widget from your launcher's widget picker, then drag a corner to resize it.",
                style = MaterialTheme.typography.bodySmall,
            )

            Spacer(Modifier.height(4.dp))
            Text("Preview", style = MaterialTheme.typography.titleMedium)

            if (loading) {
                CircularProgressIndicator()
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(preview) { item -> PreviewCard(item) }
                }
            }
        }
    }
}

@Composable
private fun PreviewCard(item: NewsItem) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
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
