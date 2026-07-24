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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kanarek.data.M3uCodec
import com.kanarek.data.SettingsStore
import com.kanarek.data.Station
import com.kanarek.data.StationKind
import com.kanarek.data.StationLogos
import com.kanarek.data.readTextCapped
import com.kanarek.player.PlayerService
import com.kanarek.player.PlayerUiState
import com.kanarek.player.VideoSize
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The radio/IPTV page. This function owns service binding, effects and persistence while visual
 * components and pure station-list state live in PlayerComponents, PlayerDialogs and
 * PlayerUiModels.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PlayerScreen(
    settings: SettingsStore,
    onMenu: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

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
        context.bindService(
            Intent(context, PlayerService::class.java),
            connection,
            Context.BIND_AUTO_CREATE,
        )
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

    var fullscreen by rememberSaveable { mutableStateOf(false) }
    var uiState by remember { mutableStateOf(PlayerScreenUiState()) }

    val stations by settings.stations.collectAsStateWithLifecycle(initialValue = emptyList())
    val favoriteStationIds by
        settings.favoriteStationIds.collectAsStateWithLifecycle(initialValue = emptySet())
    val backendUrl by settings.backendUrl.collectAsStateWithLifecycle(initialValue = "")
    val stationLogos = remember { StationLogos() }

    val tabs =
        remember(stations, favoriteStationIds) {
            stationTabs(stations, favoriteStationIds)
        }
    val showTabs = tabs.size > 1
    LaunchedEffect(tabs) {
        uiState = uiState.withValidFilter(tabs)
    }

    val notificationPermission =
        rememberLauncherForActivityResult(
            ActivityResultContracts.RequestPermission(),
        ) {}
    LaunchedEffect(Unit) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS,
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    fun persist(updated: List<Station>) {
        scope.launch { settings.setStations(updated) }
        bound?.setPlaylist(updated)
    }

    fun seedSamples() {
        scope.launch {
            val imported =
                withContext(Dispatchers.IO) {
                    listOf(
                        "playlists/tv.m3u8" to StationKind.TV,
                        "playlists/radio.m3u8" to StationKind.RADIO,
                    ).flatMap { (assetPath, kind) ->
                        runCatching {
                            context.assets
                                .open(assetPath)
                                .use { it.readTextCapped(MAX_PLAYLIST_BYTES) }
                        }.getOrNull()
                            ?.let { playlist ->
                                M3uCodec.parse(playlist).map { station ->
                                    station.copy(kind = kind)
                                }
                            } ?: emptyList()
                    }
                }
            if (imported.isEmpty()) return@launch
            val merged = (stations + imported).distinctBy(Station::streamUrl)
            persist(stationLogos.enrich(merged, backendUrl))
        }
    }

    fun toggleFavorite(station: Station) {
        val next = favoriteStationIds.toMutableSet()
        if (!next.add(station.id)) next.remove(station.id)
        scope.launch { settings.setFavoriteStationIds(next) }
    }

    fun deleteStation(station: Station) {
        persist(stations.filterNot { it.id == station.id })
        if (station.id in favoriteStationIds) {
            scope.launch {
                settings.setFavoriteStationIds(favoriteStationIds - station.id)
            }
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
                                ?.use { it.readTextCapped(MAX_PLAYLIST_BYTES) }
                        }.getOrNull()
                    } ?: return@launch
                val imported = withContext(Dispatchers.Default) { M3uCodec.parse(text) }
                if (imported.isEmpty()) return@launch
                val merged = (stations + imported).distinctBy(Station::streamUrl)
                persist(stationLogos.enrich(merged, backendUrl))
            }
        }

    val exportLauncher =
        rememberLauncherForActivityResult(
            ActivityResultContracts.CreateDocument("audio/x-mpegurl"),
        ) { uri ->
            uri ?: return@rememberLauncherForActivityResult
            scope.launch {
                withContext(Dispatchers.IO) {
                    runCatching {
                        context.contentResolver.openOutputStream(uri)?.use { output ->
                            output.write(M3uCodec.build(stations).toByteArray())
                        }
                    }
                }
            }
        }

    val currentStation = playerState.currentStation
    LaunchedEffect(currentStation?.id, favoriteStationIds, tabs) {
        uiState =
            uiState.followCurrentStation(
                station = currentStation,
                favoriteIds = favoriteStationIds,
                tabs = tabs,
            )
    }

    val visible =
        remember(stations, favoriteStationIds, uiState.filter, showTabs) {
            visibleStations(
                stations = stations,
                favoriteIds = favoriteStationIds,
                filter = uiState.filter,
                showTabs = showTabs,
            )
        }

    Scaffold(
        topBar = {
            PlayerTopBar(
                menuExpanded = uiState.menuExpanded,
                actions =
                    PlayerTopBarActions(
                        onMenu = onMenu,
                        onDiscover = {
                            uiState = uiState.copy(discoveryDialogVisible = true)
                        },
                        onImport = {
                            importLauncher.launch(
                                arrayOf(
                                    "audio/x-mpegurl",
                                    "application/vnd.apple.mpegurl",
                                    "*/*",
                                ),
                            )
                        },
                        onExport = {
                            exportLauncher.launch("kanarek-stations.m3u8")
                        },
                        onToggleMore = {
                            uiState = uiState.copy(menuExpanded = true)
                        },
                        onDismissMore = {
                            uiState = uiState.copy(menuExpanded = false)
                        },
                        onSeedSamples = {
                            uiState = uiState.copy(menuExpanded = false)
                            seedSamples()
                        },
                    ),
            )
        },
        floatingActionButton = {
            PlayerAddButton {
                uiState = uiState.copy(addDialogVisible = true)
            }
        },
        bottomBar = {
            currentStation?.let { station ->
                PlayerBottomControls(
                    station = station,
                    playerState = playerState,
                    isFavorite = station.id in favoriteStationIds,
                    actions =
                        PlayerControlActions(
                            onToggleFavorite = { toggleFavorite(station) },
                            onPrevious = { bound?.previous() },
                            onTogglePlayback = { bound?.togglePlayPause() },
                            onNext = { bound?.next() },
                        ),
                )
            }
        },
    ) { padding ->
        PlayerStationContent(
            stations = stations,
            visibleStations = visible,
            tabs = tabs,
            selectedFilter = uiState.filter,
            currentStation = currentStation,
            favoriteIds = favoriteStationIds,
            service = bound,
            videoSize = videoSize,
            fullscreen = fullscreen,
            onFullscreenChange = { fullscreen = it },
            onFilterChange = { filter ->
                uiState = uiState.copy(filter = filter)
            },
            onSeedSamples = ::seedSamples,
            stationActions =
                PlayerStationActions(
                    onPlay = { station -> bound?.playStationById(station.id) },
                    onToggleFavorite = ::toggleFavorite,
                    onEdit = { station ->
                        uiState = uiState.copy(editingStation = station)
                    },
                    onDelete = ::deleteStation,
                ),
            contentPadding = padding,
        )
    }

    if (uiState.addDialogVisible) {
        StationEditDialog(
            initial = null,
            onSave = { station ->
                persist((stations + station).distinctBy(Station::id))
                uiState = uiState.copy(addDialogVisible = false)
            },
            onDismiss = {
                uiState = uiState.copy(addDialogVisible = false)
            },
        )
    }

    uiState.editingStation?.let { current ->
        StationEditDialog(
            initial = current,
            onSave = { station ->
                persist(
                    stations
                        .map { existing ->
                            if (existing.id == current.id) station else existing
                        }.distinctBy(Station::id),
                )
                if (current.id in favoriteStationIds && station.id != current.id) {
                    scope.launch {
                        settings.setFavoriteStationIds(
                            (favoriteStationIds - current.id) + station.id,
                        )
                    }
                }
                uiState = uiState.copy(editingStation = null)
            },
            onDismiss = {
                uiState = uiState.copy(editingStation = null)
            },
        )
    }

    if (uiState.discoveryDialogVisible) {
        StationSearchDialog(
            backendUrl = backendUrl,
            existingUrls = remember(stations) { stations.map(Station::streamUrl).toSet() },
            onAdd = { station ->
                persist(
                    (stations + station.copy(kind = StationKind.RADIO))
                        .distinctBy(Station::streamUrl),
                )
            },
            onDismiss = {
                uiState = uiState.copy(discoveryDialogVisible = false)
            },
        )
    }
}

private const val MAX_PLAYLIST_BYTES = 8 * 1024 * 1024
