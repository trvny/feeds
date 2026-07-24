package com.kanarek.widget

import android.app.Activity
import android.appwidget.AppWidgetManager
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.kanarek.R
import com.kanarek.data.NewsRepository
import com.kanarek.data.SettingsStore
import com.kanarek.ui.theme.KanarekTheme
import java.net.URI
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class NewsWidgetConfigActivity : ComponentActivity() {
    private var appWidgetId = AppWidgetManager.INVALID_APPWIDGET_ID

    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setResult(Activity.RESULT_CANCELED)
        appWidgetId =
            intent?.getIntExtra(
                AppWidgetManager.EXTRA_APPWIDGET_ID,
                AppWidgetManager.INVALID_APPWIDGET_ID,
            ) ?: AppWidgetManager.INVALID_APPWIDGET_ID
        if (appWidgetId == AppWidgetManager.INVALID_APPWIDGET_ID) {
            finish()
            return
        }

        val store = NewsWidgetStore(applicationContext)
        val settings = SettingsStore(applicationContext)
        setContent {
            KanarekTheme {
                val scope = rememberCoroutineScope()
                var defaults by remember { mutableStateOf<NewsWidgetConfig?>(null) }
                var initial by remember { mutableStateOf<NewsWidgetConfig?>(null) }
                var saving by remember { mutableStateOf(false) }

                LaunchedEffect(appWidgetId) {
                    val global =
                        NewsWidgetConfig(
                            feeds =
                                runCatching { settings.feeds.first() }
                                    .getOrDefault(NewsRepository.DEFAULT_FEEDS),
                            headlines =
                                runCatching { settings.headlinesMode.first() }
                                    .getOrDefault(false),
                            intervalSeconds =
                                runCatching { settings.intervalSeconds.first() }
                                    .getOrDefault(SettingsStore.DEFAULT_INTERVAL),
                        )
                    defaults = global
                    initial =
                        withContext(Dispatchers.IO) {
                            store.config(appWidgetId)?.let {
                                NewsWidgetConfigs.normalize(it, global.feeds)
                            } ?: global
                        }
                }

                Scaffold(
                    topBar = {
                        TopAppBar(
                            title = { Text(stringResource(R.string.widget_config_title)) },
                        )
                    },
                ) { padding ->
                    val config = initial
                    val global = defaults
                    if (config == null || global == null) {
                        Column(
                            modifier =
                                Modifier
                                    .fillMaxSize()
                                    .padding(padding),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center,
                        ) {
                            CircularProgressIndicator()
                        }
                    } else {
                        NewsWidgetConfigScreen(
                            initial = config,
                            defaultFeeds = global.feeds,
                            saving = saving,
                            modifier = Modifier.padding(padding),
                            onSave = { selected ->
                                saving = true
                                scope.launch {
                                    withContext(Dispatchers.IO) {
                                        store.saveConfig(appWidgetId, selected)
                                    }
                                    KanarekWidgetProvider.update(applicationContext, appWidgetId)
                                    setResult(
                                        Activity.RESULT_OK,
                                        Intent().putExtra(
                                            AppWidgetManager.EXTRA_APPWIDGET_ID,
                                            appWidgetId,
                                        ),
                                    )
                                    finish()
                                }
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun NewsWidgetConfigScreen(
    initial: NewsWidgetConfig,
    defaultFeeds: List<String>,
    saving: Boolean,
    modifier: Modifier = Modifier,
    onSave: (NewsWidgetConfig) -> Unit,
) {
    val availableFeeds =
        remember(initial, defaultFeeds) {
            (initial.feeds + defaultFeeds).map(String::trim).filter(String::isNotEmpty).distinct()
        }
    var selectedFeeds by remember(initial) { mutableStateOf(initial.feeds.toSet()) }
    var headlines by remember(initial) { mutableStateOf(initial.headlines) }
    var intervalSeconds by remember(initial) { mutableStateOf(initial.intervalSeconds) }

    Column(
        modifier =
            modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = stringResource(R.string.widget_config_feeds),
            style = MaterialTheme.typography.titleMedium,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { selectedFeeds = availableFeeds.toSet() }) {
                Text(stringResource(R.string.select_all))
            }
            TextButton(onClick = { selectedFeeds = emptySet() }) {
                Text(stringResource(R.string.select_none))
            }
        }
        availableFeeds.forEach { feed ->
            FeedChoice(
                feed = feed,
                selected = feed in selectedFeeds,
                onToggle = {
                    selectedFeeds =
                        if (feed in selectedFeeds) {
                            selectedFeeds - feed
                        } else {
                            selectedFeeds + feed
                        }
                },
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Switch(
                checked = headlines,
                onCheckedChange = { headlines = it },
            )
            Text(stringResource(R.string.headlines_only))
        }

        Text(
            text = stringResource(R.string.widget_config_interval),
            style = MaterialTheme.typography.titleMedium,
        )
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            listOf(5, 7, 10, 15, 30).forEach { seconds ->
                FilterChip(
                    selected = intervalSeconds == seconds,
                    onClick = { intervalSeconds = seconds },
                    label = { Text(stringResource(R.string.widget_interval_seconds, seconds)) },
                )
            }
        }

        Button(
            onClick = {
                onSave(
                    NewsWidgetConfig(
                        feeds = availableFeeds.filter { it in selectedFeeds },
                        headlines = headlines,
                        intervalSeconds = intervalSeconds,
                    ),
                )
            },
            enabled = selectedFeeds.isNotEmpty() && !saving,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                stringResource(
                    if (saving) R.string.widget_config_saving else R.string.widget_config_save,
                ),
            )
        }
    }
}

@Composable
private fun FeedChoice(
    feed: String,
    selected: Boolean,
    onToggle: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(role = Role.Checkbox, onClick = onToggle)
                .padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(checked = selected, onCheckedChange = null)
        Column(Modifier.weight(1f)) {
            Text(
                text = feedLabel(feed),
                style = MaterialTheme.typography.bodyLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = feed,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

private fun feedLabel(feed: String): String =
    runCatching { URI(feed).host?.removePrefix("www.") }
        .getOrNull()
        .takeUnless { it.isNullOrBlank() } ?: feed
