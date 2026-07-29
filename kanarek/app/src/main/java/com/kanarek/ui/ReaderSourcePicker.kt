package com.kanarek.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarBorder
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.kanarek.R

@Composable
internal fun ReaderSourcePicker(
    sources: List<String>,
    selectedSources: Set<String>,
    favoriteSources: Set<String>,
    onSelectSource: (String) -> Unit,
    onClearSources: () -> Unit,
    onToggleFavorite: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (sources.isEmpty()) return

    var expanded by rememberSaveable { mutableStateOf(false) }
    val selectedLabel =
        selectedSources
            .mapNotNull { selected ->
                sources.firstOrNull { it.equals(selected, ignoreCase = true) }
            }.distinct()
            .joinToString(limit = 2, truncated = "…")

    OutlinedButton(
        onClick = { expanded = true },
        modifier =
            modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Text(
            text =
                selectedLabel.ifBlank {
                    stringResource(R.string.filter_all_sources)
                },
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }

    if (expanded) {
        SourcePickerDialog(
            sources = sources,
            selectedSources = selectedSources,
            favoriteSources = favoriteSources,
            onSelectSource = {
                onSelectSource(it)
                expanded = false
            },
            onClearSources = {
                onClearSources()
                expanded = false
            },
            onToggleFavorite = onToggleFavorite,
            onDismiss = { expanded = false },
        )
    }
}

@Composable
private fun SourcePickerDialog(
    sources: List<String>,
    selectedSources: Set<String>,
    favoriteSources: Set<String>,
    onSelectSource: (String) -> Unit,
    onClearSources: () -> Unit,
    onToggleFavorite: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var query by rememberSaveable { mutableStateOf("") }
    val sortedSources =
        remember(sources, favoriteSources, query) {
            val normalizedQuery = query.trim()
            sources
                .filter { normalizedQuery.isBlank() || it.contains(normalizedQuery, ignoreCase = true) }
                .sortedWith(
                    compareByDescending<String> { source ->
                        favoriteSources.any { it.equals(source, ignoreCase = true) }
                    }.thenBy(String.CASE_INSENSITIVE_ORDER) { it },
                )
        }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.reader_sources)) },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.close))
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text(stringResource(R.string.search_sources)) },
                    trailingIcon = {
                        if (query.isNotEmpty()) {
                            IconButton(onClick = { query = "" }) {
                                Icon(
                                    Icons.Filled.Clear,
                                    contentDescription = stringResource(R.string.clear_search),
                                )
                            }
                        }
                    },
                )
                LazyColumn(
                    modifier = Modifier.heightIn(max = 480.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    item(key = "all") {
                        SourceRow(
                            source = stringResource(R.string.filter_all_sources),
                            selected = selectedSources.isEmpty(),
                            favorite = false,
                            showFavorite = false,
                            onClick = onClearSources,
                            onToggleFavorite = {},
                        )
                    }
                    items(sortedSources, key = { it.lowercase() }) { source ->
                        SourceRow(
                            source = source,
                            selected = selectedSources.any { it.equals(source, ignoreCase = true) },
                            favorite = favoriteSources.any { it.equals(source, ignoreCase = true) },
                            showFavorite = true,
                            onClick = { onSelectSource(source) },
                            onToggleFavorite = { onToggleFavorite(source) },
                        )
                    }
                }
            }
        },
    )
}

@Composable
private fun SourceRow(
    source: String,
    selected: Boolean,
    favorite: Boolean,
    showFavorite: Boolean,
    onClick: () -> Unit,
    onToggleFavorite: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(horizontal = 8.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text = source,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        if (selected) {
            Icon(Icons.Filled.Check, contentDescription = null)
        }
        if (showFavorite) {
            IconButton(onClick = onToggleFavorite) {
                Icon(
                    if (favorite) Icons.Filled.Star else Icons.Filled.StarBorder,
                    contentDescription =
                        stringResource(
                            if (favorite) {
                                R.string.remove_source_favorite
                            } else {
                                R.string.add_source_favorite
                            },
                        ),
                )
            }
        }
    }
}
