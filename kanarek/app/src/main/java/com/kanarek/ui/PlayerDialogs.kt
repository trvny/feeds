package com.kanarek.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.kanarek.R
import com.kanarek.data.M3uCodec
import com.kanarek.data.Station
import com.kanarek.data.StationDirectory
import com.kanarek.data.StationKind
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
internal fun StationEditDialog(
    initial: Station?,
    onSave: (Station) -> Unit,
    onDismiss: () -> Unit,
) {
    var name by remember { mutableStateOf(initial?.name.orEmpty()) }
    var url by remember { mutableStateOf(initial?.streamUrl.orEmpty()) }
    var logo by remember { mutableStateOf(initial?.logoUrl.orEmpty()) }
    var group by remember { mutableStateOf(initial?.groupTitle.orEmpty()) }
    var kind by remember { mutableStateOf(initial?.kind ?: StationKind.UNKNOWN) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                stringResource(
                    if (initial == null) R.string.add_station else R.string.edit_station,
                ),
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text(stringResource(R.string.station_name)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    label = { Text(stringResource(R.string.station_url)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = logo,
                    onValueChange = { logo = it },
                    label = { Text(stringResource(R.string.station_logo_url)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = group,
                    onValueChange = { group = it },
                    label = { Text(stringResource(R.string.station_group)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    stringResource(R.string.station_kind),
                    style = MaterialTheme.typography.labelMedium,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = kind == StationKind.TV,
                        onClick = { kind = StationKind.TV },
                        label = { Text(stringResource(R.string.filter_tv)) },
                    )
                    FilterChip(
                        selected = kind == StationKind.RADIO,
                        onClick = { kind = StationKind.RADIO },
                        label = { Text(stringResource(R.string.filter_radio)) },
                    )
                    FilterChip(
                        selected = kind == StationKind.UNKNOWN,
                        onClick = { kind = StationKind.UNKNOWN },
                        label = { Text(stringResource(R.string.station_kind_auto)) },
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = name.isNotBlank() && url.isNotBlank(),
                onClick = {
                    val trimmedUrl = url.trim()
                    val urlUnchanged = initial != null && trimmedUrl == initial.streamUrl
                    onSave(
                        Station(
                            id = M3uCodec.idFor(trimmedUrl),
                            name = name.trim(),
                            streamUrl = trimmedUrl,
                            logoUrl = logo.trim().ifBlank { null },
                            groupTitle = group.trim().ifBlank { null },
                            tvgId = if (urlUnchanged) initial?.tvgId else null,
                            userAgent = if (urlUnchanged) initial?.userAgent else null,
                            referrer = if (urlUnchanged) initial?.referrer else null,
                            kind = kind,
                        ),
                    )
                },
            ) {
                Text(stringResource(android.R.string.ok))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(android.R.string.cancel))
            }
        },
    )
}

@Composable
internal fun StationSearchDialog(
    backendUrl: String,
    existingUrls: Set<String>,
    onAdd: (Station) -> Unit,
    onDismiss: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<Station>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var searched by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val directory = remember { StationDirectory() }

    fun runSearch() {
        val trimmedQuery = query.trim()
        if (trimmedQuery.isEmpty() || loading) return
        loading = true
        failed = false
        scope.launch {
            val found =
                withContext(Dispatchers.IO) {
                    runCatching {
                        directory.searchBlocking(
                            query = trimmedQuery,
                            backendUrl = backendUrl,
                        )
                    }.getOrNull()
                }
            loading = false
            searched = true
            if (found == null) {
                failed = true
                results = emptyList()
            } else {
                results = found
            }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.discover_stations)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedTextField(
                        value = query,
                        onValueChange = { query = it },
                        label = { Text(stringResource(R.string.discover_stations_hint)) },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    TextButton(
                        enabled = query.isNotBlank() && !loading,
                        onClick = ::runSearch,
                    ) {
                        Text(stringResource(R.string.discover_stations_search))
                    }
                }
                when {
                    loading -> {
                        Text(
                            stringResource(R.string.discover_stations_searching),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }

                    failed -> {
                        Text(
                            stringResource(R.string.discover_stations_error),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }

                    searched && results.isEmpty() -> {
                        Text(
                            stringResource(R.string.discover_stations_none),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
                LazyColumn(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    items(results, key = Station::id) { station ->
                        StationSearchResult(
                            station = station,
                            alreadyAdded = station.streamUrl in existingUrls,
                            onAdd = { onAdd(station) },
                        )
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.close))
            }
        },
    )
}

@Composable
private fun StationSearchResult(
    station: Station,
    alreadyAdded: Boolean,
    onAdd: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        StationLogo(station, size = 32.dp)
        Column(Modifier.weight(1f)) {
            Text(
                station.name,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (!station.groupTitle.isNullOrBlank()) {
                Text(
                    station.groupTitle,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (alreadyAdded) {
            Text(
                stringResource(R.string.discover_stations_added),
                style = MaterialTheme.typography.labelSmall,
            )
        } else {
            IconButton(onClick = onAdd) {
                Icon(
                    Icons.Filled.Add,
                    contentDescription = stringResource(R.string.discover_stations_add),
                )
            }
        }
    }
}
