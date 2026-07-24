package com.kanarek.ui

import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.kanarek.R
import com.kanarek.data.ArticleState
import com.kanarek.data.ArticleStateStore
import com.kanarek.data.StorageDataManager
import com.kanarek.data.StorageUsage
import kotlinx.coroutines.launch

private enum class StorageAction { MEASURE, FEEDS, IMAGES, HISTORY, SAVED }

@Composable
internal fun StorageScreen(
    articleState: ArticleState,
    articleStateStore: ArticleStateStore,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val storage = remember(context) { StorageDataManager(context) }
    var usage by remember { mutableStateOf<StorageUsage?>(null) }
    var activeAction by remember { mutableStateOf<StorageAction?>(StorageAction.MEASURE) }
    var confirmHistory by remember { mutableStateOf(false) }
    var confirmSaved by remember { mutableStateOf(false) }

    suspend fun refreshUsage() {
        usage = storage.usage()
    }

    fun runAction(
        action: StorageAction,
        block: suspend () -> Unit,
    ) {
        scope.launch {
            activeAction = action
            try {
                block()
                refreshUsage()
            } finally {
                activeAction = null
            }
        }
    }

    LaunchedEffect(storage) {
        try {
            refreshUsage()
        } finally {
            activeAction = null
        }
    }

    Column(
        modifier =
            modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = stringResource(R.string.storage_usage_hint),
            style = MaterialTheme.typography.bodyMedium,
        )

        CacheCard(
            title = stringResource(R.string.feed_cache),
            bytes = usage?.feedCacheBytes,
            busy = activeAction == StorageAction.FEEDS,
            enabled = activeAction == null,
            onClear = {
                runAction(StorageAction.FEEDS) { storage.clearFeedCache() }
            },
        )
        CacheCard(
            title = stringResource(R.string.image_cache),
            bytes = usage?.imageCacheBytes,
            busy = activeAction == StorageAction.IMAGES,
            enabled = activeAction == null,
            onClear = {
                runAction(StorageAction.IMAGES) { storage.clearImageCache() }
            },
        )

        Card(Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = stringResource(R.string.article_history),
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    text =
                        stringResource(
                            R.string.article_history_summary,
                            articleState.readIds.size,
                            articleState.hiddenIds.size,
                            articleState.savedArticles.size,
                        ),
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedButton(
                    onClick = { confirmHistory = true },
                    enabled = activeAction == null,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.clear_read_hidden))
                }
                Button(
                    onClick = { confirmSaved = true },
                    enabled = activeAction == null,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.clear_saved_articles))
                }
            }
        }

        if (activeAction == StorageAction.MEASURE) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator()
            }
        }
        Spacer(Modifier.height(8.dp))
    }

    if (confirmHistory) {
        AlertDialog(
            onDismissRequest = { confirmHistory = false },
            title = { Text(stringResource(R.string.clear_history_confirm_title)) },
            text = { Text(stringResource(R.string.clear_history_confirm_message)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmHistory = false
                        runAction(StorageAction.HISTORY) {
                            articleStateStore.clearReadAndHidden()
                        }
                    },
                ) {
                    Text(stringResource(R.string.clear))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmHistory = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    if (confirmSaved) {
        AlertDialog(
            onDismissRequest = { confirmSaved = false },
            title = { Text(stringResource(R.string.clear_saved_confirm_title)) },
            text = { Text(stringResource(R.string.clear_saved_confirm_message)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmSaved = false
                        runAction(StorageAction.SAVED) {
                            articleStateStore.clearSavedArticles()
                        }
                    },
                ) {
                    Text(stringResource(R.string.clear))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmSaved = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }
}

@Composable
private fun CacheCard(
    title: String,
    bytes: Long?,
    busy: Boolean,
    enabled: Boolean,
    onClear: () -> Unit,
) {
    val context = LocalContext.current
    Card(Modifier.fillMaxWidth()) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(
                    text =
                        bytes?.let {
                            stringResource(
                                R.string.storage_size_approx,
                                Formatter.formatShortFileSize(context, it),
                            )
                        } ?: stringResource(R.string.storage_calculating),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            if (busy) {
                CircularProgressIndicator()
            } else {
                OutlinedButton(onClick = onClear, enabled = enabled) {
                    Text(stringResource(R.string.clear))
                }
            }
        }
    }
}
