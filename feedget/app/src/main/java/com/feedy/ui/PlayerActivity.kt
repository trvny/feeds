package com.feedy.ui

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.FileUpload
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.BottomAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.feedy.R
import com.feedy.data.M3uCodec
import com.feedy.data.SettingsStore
import com.feedy.data.Station
import com.feedy.player.PlayerService
import com.feedy.player.PlayerUiState
import com.feedy.ui.theme.FeedyTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class PlayerActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.isNavigationBarContrastEnforced = false
        }
        val settings = SettingsStore(applicationContext)
        setContent {
            FeedyTheme {
                PlayerScreen(settings = settings)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlayerScreen(settings: SettingsStore) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // Bind directly to the running/starting service — same process, so a plain Binder is enough.
    var bound by remember { mutableStateOf<PlayerService?>(null) }
    DisposableEffect(Unit) {
        val connection = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
                bound = (binder as? PlayerService.LocalBinder)?.service
            }
            override fun onServiceDisconnected(name: ComponentName?) {
                bound = null
            }
        }
        context.bindService(Intent(context, PlayerService::class.java), connection, Context.BIND_AUTO_CREATE)
        onDispose { context.unbindService(connection) }
    }

    var playerState by remember { mutableStateOf(PlayerUiState()) }
    LaunchedEffect(bound) {
        bound?.uiState?.collect { playerState = it }
    }

    // The persisted list is the source of truth for the editor; the service mirrors it once
    // bound and whenever it changes here.
    val stations by settings.stations.collectAsStateWithLifecycle(initialValue = emptyList())

    val notifPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    LaunchedEffect(Unit) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    fun persist(updated: List<Station>) {
        scope.launch { settings.setStations(updated) }
        bound?.setPlaylist(updated)
    }

    fun play(station: Station) {
        bound?.playStationById(station.id)
    }

    var editing by remember { mutableStateOf<Station?>(null) }
    var showAdd by remember { mutableStateOf(false) }

    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        scope.launch {
            val text = withContext(Dispatchers.IO) {
                runCatching { context.contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() } }.getOrNull()
            } ?: return@launch
            val imported = M3uCodec.parse(text)
            if (imported.isEmpty()) return@launch
            val merged = (stations + imported).distinctBy { it.streamUrl }
            persist(merged)
        }
    }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/x-mpegurl")) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        scope.launch {
            withContext(Dispatchers.IO) {
                runCatching {
                    context.contentResolver.openOutputStream(uri)?.use { it.write(M3uCodec.build(stations).toByteArray()) }
                }
            }
        }
    }

    val currentStation = playerState.currentStation

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.player_title)) },
                actions = {
                    IconButton(onClick = { importLauncher.launch(arrayOf("audio/x-mpegurl", "application/vnd.apple.mpegurl", "*/*")) }) {
                        Icon(Icons.Filled.FileUpload, contentDescription = stringResource(R.string.import_m3u))
                    }
                    IconButton(onClick = { exportLauncher.launch("feedy-stations.m3u8") }) {
                        Icon(Icons.Filled.FileDownload, contentDescription = stringResource(R.string.export_m3u))
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAdd = true }) {
                Icon(Icons.Filled.Add, contentDescription = stringResource(R.string.add_station))
            }
        },
        bottomBar = {
            if (currentStation != null) {
                BottomAppBar {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        StationLogo(currentStation.logoUrl, size = 36.dp)
                        Column(Modifier.weight(1f).padding(horizontal = 8.dp)) {
                            Text(
                                currentStation.name,
                                style = MaterialTheme.typography.titleSmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            if (!currentStation.groupTitle.isNullOrBlank()) {
                                Text(
                                    currentStation.groupTitle,
                                    style = MaterialTheme.typography.bodySmall,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                        IconButton(onClick = { bound?.previous() }) {
                            Icon(Icons.Filled.SkipPrevious, contentDescription = stringResource(R.string.action_previous))
                        }
                        IconButton(onClick = { bound?.togglePlayPause() }) {
                            Icon(
                                if (playerState.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                                contentDescription = stringResource(if (playerState.isPlaying) R.string.action_pause else R.string.action_play),
                            )
                        }
                        IconButton(onClick = { bound?.next() }) {
                            Icon(Icons.Filled.SkipNext, contentDescription = stringResource(R.string.action_next))
                        }
                    }
                }
            }
        },
    ) { padding ->
        if (stations.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Text(stringResource(R.string.no_stations), style = MaterialTheme.typography.bodyMedium)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = padding,
            ) {
                items(stations, key = { it.id }) { station ->
                    StationRow(
                        station = station,
                        isCurrent = station.id == currentStation?.id,
                        onClick = { play(station) },
                        onEdit = { editing = station },
                        onDelete = { persist(stations.filterNot { it.id == station.id }) },
                    )
                }
            }
        }
    }

    if (showAdd) {
        StationEditDialog(
            initial = null,
            onSave = { s -> persist(stations + s); showAdd = false },
            onDismiss = { showAdd = false },
        )
    }
    editing?.let { current ->
        StationEditDialog(
            initial = current,
            onSave = { s -> persist(stations.map { if (it.id == current.id) s else it }.distinctBy { it.id }); editing = null },
            onDismiss = { editing = null },
        )
    }
}

@Composable
private fun StationRow(
    station: Station,
    isCurrent: Boolean,
    onClick: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        StationLogo(station.logoUrl, size = 44.dp)
        Column(Modifier.weight(1f)) {
            Text(
                station.name,
                style = if (isCurrent) MaterialTheme.typography.titleSmall else MaterialTheme.typography.bodyLarge,
                color = if (isCurrent) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (!station.groupTitle.isNullOrBlank()) {
                Text(station.groupTitle, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        IconButton(onClick = onEdit) { Icon(Icons.Filled.Edit, contentDescription = stringResource(R.string.edit_station)) }
        IconButton(onClick = onDelete) { Icon(Icons.Filled.Delete, contentDescription = stringResource(R.string.delete_station)) }
    }
}

@Composable
private fun StationLogo(logoUrl: String?, size: Dp) {
    val fallback = painterResource(R.drawable.ic_radio_fallback)
    Box(
        modifier = Modifier
            .size(size)
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        AsyncImage(
            model = logoUrl?.takeIf { it.isNotBlank() },
            contentDescription = null,
            error = fallback,
            fallback = fallback,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop,
        )
    }
}

@Composable
private fun StationEditDialog(
    initial: Station?,
    onSave: (Station) -> Unit,
    onDismiss: () -> Unit,
) {
    var name by remember { mutableStateOf(initial?.name.orEmpty()) }
    var url by remember { mutableStateOf(initial?.streamUrl.orEmpty()) }
    var logo by remember { mutableStateOf(initial?.logoUrl.orEmpty()) }
    var group by remember { mutableStateOf(initial?.groupTitle.orEmpty()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(if (initial == null) R.string.add_station else R.string.edit_station)) },
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
            }
        },
        confirmButton = {
            TextButton(
                enabled = name.isNotBlank() && url.isNotBlank(),
                onClick = {
                    val trimmedUrl = url.trim()
                    // Headers aren't editable in this dialog (no UI fields for them); carry them
                    // over so editing name/logo/group on an imported station with custom headers
                    // doesn't silently strip them — but only while the URL they were parsed for
                    // is unchanged, since a header pinned to one stream is meaningless on another.
                    val urlUnchanged = initial != null && trimmedUrl == initial.streamUrl
                    onSave(
                        Station(
                            id = M3uCodec.idFor(trimmedUrl),
                            name = name.trim(),
                            streamUrl = trimmedUrl,
                            logoUrl = logo.trim().ifBlank { null },
                            groupTitle = group.trim().ifBlank { null },
                            userAgent = if (urlUnchanged) initial?.userAgent else null,
                            referrer = if (urlUnchanged) initial?.referrer else null,
                        ),
                    )
                },
            ) { Text(stringResource(android.R.string.ok)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}
