package com.kanarek.ui

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Build
import android.os.IBinder
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.FileUpload
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Radio
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.BottomAppBar
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.kanarek.R
import com.kanarek.data.M3uCodec
import com.kanarek.data.SettingsStore
import com.kanarek.data.Station
import com.kanarek.data.StationKind
import com.kanarek.data.StationDirectory
import com.kanarek.data.StationLogos
import com.kanarek.player.PlayerService
import com.kanarek.player.PlayerUiState
import com.kanarek.player.VideoSize
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The radio/IPTV half of the app, hosted as a page of [com.kanarek.HomeActivity]'s pager
 * (formerly the standalone PlayerActivity). [onMenu] opens the app-level navigation drawer.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
internal fun PlayerScreen(
    settings: SettingsStore,
    onMenu: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // Bind directly to the running/starting service — same process, so a plain Binder is enough.
    var bound by remember { mutableStateOf<PlayerService?>(null) }
    DisposableEffect(Unit) {
        val connection =
            object : ServiceConnection {
                override fun onServiceConnected(
                    name: ComponentName?,
                    binder: IBinder?,
                ) {
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

    var videoSize by remember { mutableStateOf(VideoSize()) }
    LaunchedEffect(bound) {
        bound?.videoSize?.collect { videoSize = it }
    }

    // TV / Radio split of the station list. Only offered when the list actually holds both
    // kinds; UNKNOWN counts as possibly-video, so it lives under the TV tab.
    var kindTab by remember { mutableStateOf(StationTab.TV) }

    // The persisted list is the source of truth for the editor; the service mirrors it once
    // bound and whenever it changes here.
    val stations by settings.stations.collectAsStateWithLifecycle(initialValue = emptyList())
    val backendUrl by settings.backendUrl.collectAsStateWithLifecycle(initialValue = "")
    val stationLogos = remember { StationLogos() }

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

    // Load one of the bundled seed playlists (assets/playlists/*.m3u8) into the station
    // list, de-duped by stream URL. Still user-initiated (empty-state button), so the
    // "assets are not auto-seeded" invariant holds — nothing loads without a tap.
    fun seedFromAsset(
        assetPath: String,
        kind: StationKind,
    ) {
        scope.launch {
            val text =
                withContext(Dispatchers.IO) {
                    runCatching {
                        context.assets
                            .open(assetPath)
                            .bufferedReader()
                            .use { it.readText() }
                    }.getOrNull()
                } ?: return@launch
            // Tag every seeded station with its kind so the TV/Radio filter and the video surface
            // know what they're dealing with; the bundled M3Us don't carry kanarek-kind themselves.
            val imported = M3uCodec.parse(text).map { it.copy(kind = kind) }
            if (imported.isEmpty()) return@launch
            val merged = (stations + imported).distinctBy { it.streamUrl }
            persist(stationLogos.enrich(merged, backendUrl))
        }
    }

    fun play(station: Station) {
        bound?.playStationById(station.id)
    }

    var editing by remember { mutableStateOf<Station?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var showDiscover by remember { mutableStateOf(false) }
    var showMenu by remember { mutableStateOf(false) }

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
                val imported = M3uCodec.parse(text)
                if (imported.isEmpty()) return@launch
                val merged = (stations + imported).distinctBy { it.streamUrl }
                persist(stationLogos.enrich(merged, backendUrl))
            }
        }

    val exportLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/x-mpegurl")) { uri ->
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
                navigationIcon = {
                    IconButton(onClick = onMenu) {
                        Icon(Icons.Filled.Menu, contentDescription = stringResource(R.string.menu))
                    }
                },
                actions = {
                    IconButton(onClick = { showDiscover = true }) {
                        Icon(Icons.Filled.Search, contentDescription = stringResource(R.string.discover_stations))
                    }
                    IconButton(onClick = { importLauncher.launch(arrayOf("audio/x-mpegurl", "application/vnd.apple.mpegurl", "*/*")) }) {
                        Icon(Icons.Filled.FileUpload, contentDescription = stringResource(R.string.import_m3u))
                    }
                    IconButton(onClick = { exportLauncher.launch("kanarek-stations.m3u8") }) {
                        Icon(Icons.Filled.FileDownload, contentDescription = stringResource(R.string.export_m3u))
                    }
                    // Sample loaders live here too (not just the empty state) so you can add the
                    // sample radio after already loading the sample TV list, and vice versa.
                    IconButton(onClick = { showMenu = true }) {
                        Icon(Icons.Filled.MoreVert, contentDescription = stringResource(R.string.more_options))
                    }
                    DropdownMenu(expanded = showMenu, onDismissRequest = { showMenu = false }) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.seed_tv)) },
                            onClick = {
                                showMenu = false
                                seedFromAsset("playlists/tv.m3u8", StationKind.TV)
                            },
                        )
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.seed_radio)) },
                            onClick = {
                                showMenu = false
                                seedFromAsset("playlists/radio.m3u8", StationKind.RADIO)
                            },
                        )
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
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        StationLogo(currentStation.logoUrl, currentStation.streamUrl, size = 36.dp)
                        Column(Modifier.weight(1f).padding(horizontal = 8.dp)) {
                            Text(
                                currentStation.name,
                                style = MaterialTheme.typography.titleSmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            val subtitle = playerState.nowPlaying?.takeIf { it.isNotBlank() } ?: currentStation.groupTitle
                            if (!subtitle.isNullOrBlank()) {
                                Text(
                                    subtitle,
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
                                contentDescription =
                                    stringResource(
                                        if (playerState.isPlaying) R.string.action_pause else R.string.action_play,
                                    ),
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
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(stringResource(R.string.no_stations), style = MaterialTheme.typography.bodyMedium)
                    OutlinedButton(onClick = { seedFromAsset("playlists/tv.m3u8", StationKind.TV) }) {
                        Text(stringResource(R.string.seed_tv))
                    }
                    OutlinedButton(onClick = { seedFromAsset("playlists/radio.m3u8", StationKind.RADIO) }) {
                        Text(stringResource(R.string.seed_radio))
                    }
                }
            }
        } else {
            // Two buckets: video (TV + untagged/possibly-video) and audio (radio). Tabs only
            // appear when both buckets are non-empty — a pure-radio or pure-TV list stays flat.
            val tvBucket = remember(stations) { stations.filter { it.kind != StationKind.RADIO } }
            val radioBucket = remember(stations) { stations.filter { it.kind == StationKind.RADIO } }
            val showTabs = tvBucket.isNotEmpty() && radioBucket.isNotEmpty()
            val visible =
                remember(stations, kindTab, showTabs) {
                    if (!showTabs) {
                        stations
                    } else {
                        when (kindTab) {
                            StationTab.TV -> tvBucket
                            StationTab.RADIO -> radioBucket
                        }
                    }
                }

            // Video output for the current channel. Radio never shows it; TV shows it as soon as
            // it's selected; an untagged (unknown) stream shows it only once actual video decodes.
            // Without this surface the ExoPlayer had nowhere to draw, so TV played as sound only.
            val cur = currentStation
            val showVideo = cur != null && cur.kind != StationKind.RADIO && (cur.kind == StationKind.TV || videoSize.hasVideo)

            Column(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(padding),
            ) {
                if (showVideo) {
                    VideoArea(service = bound, videoSize = videoSize)
                } else if (cur != null) {
                    // Audio-only (radio / untagged stream with no decoded video yet): instead of a
                    // black video box, show the station's logo, name, and — when the stream sends
                    // ICY/ID3 metadata — the currently playing track.
                    NowPlayingArea(station = cur, nowPlaying = playerState.nowPlaying)
                }
                if (showTabs) {
                    KindTabs(selected = kindTab, onSelect = { kindTab = it })
                }

                // Group the flat list by group-title into first-appearance order. Only actually
                // sections it when there's more than one group — a radio / hand-added list with no
                // groups (or a single group) stays a plain flat list, exactly as before. Sections
                // start collapsed: an imported tv.m3u8 with hundreds of channels opens as a short
                // list of group headers you expand on demand, instead of one endless scroll.
                val groups = remember(visible) { groupStations(visible) }
                val sectioned = groups.size > 1
                val collapsed = remember { mutableStateMapOf<String, Boolean>() }
                LazyColumn(modifier = Modifier.weight(1f).fillMaxSize()) {
                    if (!sectioned) {
                        items(visible, key = { it.id }) { station ->
                            StationRow(
                                station = station,
                                isCurrent = station.id == currentStation?.id,
                                onClick = { play(station) },
                                onEdit = { editing = station },
                                onDelete = { persist(stations.filterNot { it.id == station.id }) },
                            )
                        }
                    } else {
                        groups.forEach { (group, list) ->
                            val key = group ?: NO_GROUP_KEY
                            val isCollapsed = collapsed[key] ?: true
                            stickyHeader(key = "hdr:$key") {
                                GroupHeader(
                                    title = group ?: stringResource(R.string.group_ungrouped),
                                    count = list.size,
                                    collapsed = isCollapsed,
                                    onToggle = { collapsed[key] = !isCollapsed },
                                )
                            }
                            if (!isCollapsed) {
                                items(list, key = { it.id }) { station ->
                                    StationRow(
                                        station = station,
                                        isCurrent = station.id == currentStation?.id,
                                        onClick = { play(station) },
                                        onEdit = { editing = station },
                                        onDelete = { persist(stations.filterNot { it.id == station.id }) },
                                        showGroupSubtitle = false,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (showAdd) {
        StationEditDialog(
            initial = null,
            onSave = { s ->
                persist((stations + s).distinctBy { it.id })
                showAdd = false
            },
            onDismiss = { showAdd = false },
        )
    }
    editing?.let { current ->
        StationEditDialog(
            initial = current,
            onSave = { s ->
                persist(stations.map { if (it.id == current.id) s else it }.distinctBy { it.id })
                editing = null
            },
            onDismiss = { editing = null },
        )
    }
    if (showDiscover) {
        StationSearchDialog(
            backendUrl = backendUrl,
            existingUrls = remember(stations) { stations.map { it.streamUrl }.toSet() },
            // Radio Browser is a radio-only catalog, so anything added from Discover is radio.
            onAdd = { s -> persist((stations + s.copy(kind = StationKind.RADIO)).distinctBy { it.streamUrl }) },
            onDismiss = { showDiscover = false },
        )
    }
}

/** Which bucket of the station list is showing: video streams (TV + untagged) or audio (radio). */
private enum class StationTab { TV, RADIO }

@Composable
private fun KindTabs(
    selected: StationTab,
    onSelect: (StationTab) -> Unit,
) {
    TabRow(selectedTabIndex = if (selected == StationTab.TV) 0 else 1) {
        Tab(
            selected = selected == StationTab.TV,
            onClick = { onSelect(StationTab.TV) },
            text = { Text(stringResource(R.string.filter_tv)) },
            icon = { Icon(Icons.Filled.Tv, contentDescription = null) },
        )
        Tab(
            selected = selected == StationTab.RADIO,
            onClick = { onSelect(StationTab.RADIO) },
            text = { Text(stringResource(R.string.filter_radio)) },
            icon = { Icon(Icons.Filled.Radio, contentDescription = null) },
        )
    }
}

/**
 * What the video area shows when the current stream is audio-only: the station's logo (large),
 * name, group, and — when the stream carries ICY/ID3 metadata — the track it's playing right now,
 * marquee-scrolled when it doesn't fit. Nothing here is required to exist: a silent stream just
 * shows logo + name.
 */
@Composable
private fun NowPlayingArea(
    station: Station,
    nowPlaying: String?,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        StationLogo(station.logoUrl, station.streamUrl, size = 72.dp)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                station.name,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (!station.groupTitle.isNullOrBlank()) {
                Text(
                    station.groupTitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (!nowPlaying.isNullOrBlank()) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Icon(
                        Icons.Filled.MusicNote,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(16.dp),
                    )
                    Text(
                        nowPlaying,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.primary,
                        maxLines = 1,
                        modifier = Modifier.basicMarquee(),
                    )
                }
            }
        }
    }
}

/**
 * The video output for the current TV channel. Hosts a [android.view.SurfaceView] and forwards its
 * [android.view.Surface] to the one [PlayerService] player — the missing piece that made TV play
 * as sound only. Sized to the decoded aspect ratio once known, 16:9 until then. The surface is
 * (re)attached in [AndroidView]'s update block so it also connects when the service binds after the
 * view is already on screen, and detached in surfaceDestroyed so it's released cleanly.
 */
@Composable
private fun VideoArea(
    service: PlayerService?,
    videoSize: VideoSize,
) {
    val ratio = if (videoSize.hasVideo) videoSize.width.toFloat() / videoSize.height else 16f / 9f
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .aspectRatio(ratio)
                .background(Color.Black),
    ) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                android.view.SurfaceView(ctx).apply {
                    holder.addCallback(
                        object : android.view.SurfaceHolder.Callback {
                            override fun surfaceCreated(holder: android.view.SurfaceHolder) {
                                service?.setVideoSurface(holder.surface)
                            }

                            override fun surfaceChanged(
                                holder: android.view.SurfaceHolder,
                                format: Int,
                                width: Int,
                                height: Int,
                            ) = Unit

                            override fun surfaceDestroyed(holder: android.view.SurfaceHolder) {
                                service?.setVideoSurface(null)
                            }
                        },
                    )
                }
            },
            update = { view ->
                val surface = view.holder.surface
                if (surface != null && surface.isValid) service?.setVideoSurface(surface)
            },
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
    showGroupSubtitle: Boolean = true,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        StationLogo(station.logoUrl, station.streamUrl, size = 44.dp)
        Column(Modifier.weight(1f)) {
            Text(
                station.name,
                style = if (isCurrent) MaterialTheme.typography.titleSmall else MaterialTheme.typography.bodyLarge,
                color = if (isCurrent) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (showGroupSubtitle && !station.groupTitle.isNullOrBlank()) {
                Text(station.groupTitle, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        IconButton(onClick = onEdit) { Icon(Icons.Filled.Edit, contentDescription = stringResource(R.string.edit_station)) }
        IconButton(onClick = onDelete) { Icon(Icons.Filled.Delete, contentDescription = stringResource(R.string.delete_station)) }
    }
}

private const val NO_GROUP_KEY = "\u0000ungrouped"

/**
 * Bucket a flat station list by non-blank [Station.groupTitle], preserving first-appearance
 * order of both the groups and the stations within each. Pure list logic, no Android deps.
 */
private fun groupStations(stations: List<Station>): List<Pair<String?, List<Station>>> {
    val order = LinkedHashMap<String?, MutableList<Station>>()
    for (s in stations) {
        val g = s.groupTitle?.takeIf { it.isNotBlank() }
        order.getOrPut(g) { mutableListOf() }.add(s)
    }
    return order.entries.map { it.key to it.value.toList() }
}

@Composable
private fun GroupHeader(
    title: String,
    count: Int,
    collapsed: Boolean,
    onToggle: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .clickable(onClick = onToggle)
                .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(
            if (collapsed) Icons.Filled.ExpandMore else Icons.Filled.ExpandLess,
            contentDescription = stringResource(if (collapsed) R.string.group_expand else R.string.group_collapse),
        )
        Text(
            title,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.primary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        Text(
            count.toString(),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/**
 * A station's logo, with a favicon fallback chain: the M3U/tvg logo when set, else the stream
 * host's favicon via Google s2 (always PNG, so Coil can decode it), else DuckDuckGo's icon
 * service, else the built-in glyph. Covers the bundled seed playlists' entries that ship without
 * a `tvg-logo` — most stream hosts at least serve a recognizable favicon.
 */
@Composable
private fun StationLogo(
    logoUrl: String?,
    streamUrl: String?,
    size: Dp,
) {
    val fallback = painterResource(R.drawable.ic_radio_fallback)
    val candidates =
        remember(logoUrl, streamUrl) {
            buildList {
                logoUrl?.takeIf { it.isNotBlank() }?.let { add(it) }
                streamUrl
                    ?.let { runCatching { java.net.URI(it).host }.getOrNull() }
                    ?.takeIf { it.isNotBlank() }
                    ?.let { host ->
                        add("https://www.google.com/s2/favicons?domain=$host&sz=128")
                        add("https://icons.duckduckgo.com/ip3/$host.ico")
                    }
            }
        }
    var attempt by remember(candidates) { mutableIntStateOf(0) }
    Box(
        modifier =
            Modifier
                .size(size)
                .clip(RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        AsyncImage(
            model = candidates.getOrNull(attempt),
            contentDescription = null,
            onError = { if (attempt < candidates.lastIndex) attempt++ },
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
    var kind by remember { mutableStateOf(initial?.kind ?: StationKind.UNKNOWN) }

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
                Text(stringResource(R.string.station_kind), style = MaterialTheme.typography.labelMedium)
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
                            tvgId = if (urlUnchanged) initial?.tvgId else null,
                            userAgent = if (urlUnchanged) initial?.userAgent else null,
                            referrer = if (urlUnchanged) initial?.referrer else null,
                            kind = kind,
                        ),
                    )
                },
            ) { Text(stringResource(android.R.string.ok)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

/**
 * Search the Radio Browser catalog (via [StationDirectory] -> the Worker's `/stations/search`)
 * and let the user add hits to their station list — a much bigger catalog than the bundled seed
 * playlists, without hand-curating stations. Network calls only run through the repository,
 * never inline in the composable.
 */
@Composable
private fun StationSearchDialog(
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
        val q = query.trim()
        if (q.isEmpty() || loading) return
        loading = true
        failed = false
        scope.launch {
            val found =
                withContext(Dispatchers.IO) {
                    runCatching { directory.searchBlocking(query = q, backendUrl = backendUrl) }.getOrNull()
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
                    TextButton(enabled = query.isNotBlank() && !loading, onClick = { runSearch() }) {
                        Text(stringResource(R.string.discover_stations_search))
                    }
                }
                when {
                    loading -> Text(stringResource(R.string.discover_stations_searching), style = MaterialTheme.typography.bodySmall)
                    failed -> Text(stringResource(R.string.discover_stations_error), style = MaterialTheme.typography.bodySmall)
                    searched && results.isEmpty() ->
                        Text(stringResource(R.string.discover_stations_none), style = MaterialTheme.typography.bodySmall)
                }
                LazyColumn(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    items(results, key = { it.id }) { s ->
                        val alreadyAdded = s.streamUrl in existingUrls
                        Row(
                            modifier =
                                Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            StationLogo(s.logoUrl, s.streamUrl, size = 32.dp)
                            Column(Modifier.weight(1f)) {
                                Text(s.name, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                if (!s.groupTitle.isNullOrBlank()) {
                                    Text(
                                        s.groupTitle,
                                        style = MaterialTheme.typography.bodySmall,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                }
                            }
                            if (alreadyAdded) {
                                Text(stringResource(R.string.discover_stations_added), style = MaterialTheme.typography.labelSmall)
                            } else {
                                IconButton(onClick = { onAdd(s) }) {
                                    Icon(Icons.Filled.Add, contentDescription = stringResource(R.string.discover_stations_add))
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.close)) } },
    )
}
