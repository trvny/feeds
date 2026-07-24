package com.kanarek.ui

import android.content.Context
import android.content.pm.ActivityInfo
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.FileUpload
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Radio
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarBorder
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material3.BottomAppBar
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import coil.compose.AsyncImage
import com.kanarek.R
import com.kanarek.cast.CastButton
import com.kanarek.data.Favicons
import com.kanarek.data.Station
import com.kanarek.data.StationKind
import com.kanarek.player.PlayerService
import com.kanarek.player.PlayerUiState
import com.kanarek.player.VideoSize

internal data class PlayerTopBarActions(
    val onMenu: () -> Unit,
    val onDiscover: () -> Unit,
    val onImport: () -> Unit,
    val onExport: () -> Unit,
    val onToggleMore: () -> Unit,
    val onDismissMore: () -> Unit,
    val onSeedSamples: () -> Unit,
)

internal data class PlayerControlActions(
    val onToggleFavorite: () -> Unit,
    val onPrevious: () -> Unit,
    val onTogglePlayback: () -> Unit,
    val onNext: () -> Unit,
)

internal data class PlayerStationActions(
    val onPlay: (Station) -> Unit,
    val onToggleFavorite: (Station) -> Unit,
    val onEdit: (Station) -> Unit,
    val onDelete: (Station) -> Unit,
)

@Composable
internal fun PlayerTopBar(
    menuExpanded: Boolean,
    actions: PlayerTopBarActions,
) {
    TopAppBar(
        title = { Text(stringResource(R.string.player_title)) },
        navigationIcon = {
            IconButton(onClick = actions.onMenu) {
                Icon(Icons.Filled.Menu, contentDescription = stringResource(R.string.menu))
            }
        },
        actions = {
            CastButton()
            IconButton(onClick = actions.onDiscover) {
                Icon(
                    Icons.Filled.Search,
                    contentDescription = stringResource(R.string.discover_stations),
                )
            }
            IconButton(onClick = actions.onImport) {
                Icon(
                    Icons.Filled.FileUpload,
                    contentDescription = stringResource(R.string.import_m3u),
                )
            }
            IconButton(onClick = actions.onExport) {
                Icon(
                    Icons.Filled.FileDownload,
                    contentDescription = stringResource(R.string.export_m3u),
                )
            }
            IconButton(onClick = actions.onToggleMore) {
                Icon(
                    Icons.Filled.MoreVert,
                    contentDescription = stringResource(R.string.more_options),
                )
            }
            DropdownMenu(
                expanded = menuExpanded,
                onDismissRequest = actions.onDismissMore,
            ) {
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.seed_samples)) },
                    onClick = actions.onSeedSamples,
                )
            }
        },
    )
}

@Composable
internal fun PlayerAddButton(onClick: () -> Unit) {
    FloatingActionButton(onClick = onClick) {
        Icon(Icons.Filled.Add, contentDescription = stringResource(R.string.add_station))
    }
}

@Composable
internal fun PlayerBottomControls(
    station: Station,
    playerState: PlayerUiState,
    isFavorite: Boolean,
    actions: PlayerControlActions,
) {
    BottomAppBar {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            StationLogo(station, size = 36.dp)
            Column(
                Modifier
                    .weight(1f)
                    .padding(horizontal = 8.dp),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    KindBadge(station.kind, size = 14.dp)
                    Text(
                        station.name,
                        style = MaterialTheme.typography.titleSmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                val subtitle = playerState.nowPlaying ?: station.groupTitle
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            IconButton(onClick = actions.onToggleFavorite) {
                Icon(
                    if (isFavorite) Icons.Filled.Star else Icons.Filled.StarBorder,
                    contentDescription =
                        stringResource(
                            if (isFavorite) {
                                R.string.remove_station_favorite
                            } else {
                                R.string.add_station_favorite
                            },
                        ),
                )
            }
            IconButton(onClick = actions.onPrevious) {
                Icon(
                    Icons.Filled.SkipPrevious,
                    contentDescription = stringResource(R.string.action_previous),
                )
            }
            IconButton(onClick = actions.onTogglePlayback) {
                Icon(
                    if (playerState.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                    contentDescription =
                        stringResource(
                            if (playerState.isPlaying) {
                                R.string.action_pause
                            } else {
                                R.string.action_play
                            },
                        ),
                )
            }
            IconButton(onClick = actions.onNext) {
                Icon(
                    Icons.Filled.SkipNext,
                    contentDescription = stringResource(R.string.action_next),
                )
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
internal fun PlayerStationContent(
    stations: List<Station>,
    visibleStations: List<Station>,
    tabs: List<StationFilter>,
    selectedFilter: StationFilter,
    currentStation: Station?,
    favoriteIds: Set<String>,
    service: PlayerService?,
    videoSize: VideoSize,
    fullscreen: Boolean,
    onFullscreenChange: (Boolean) -> Unit,
    onFilterChange: (StationFilter) -> Unit,
    onSeedSamples: () -> Unit,
    stationActions: PlayerStationActions,
    contentPadding: PaddingValues,
) {
    if (stations.isEmpty()) {
        EmptyStationContent(
            onSeedSamples = onSeedSamples,
            contentPadding = contentPadding,
        )
        return
    }

    val showVideo = currentStation != null && currentStation.kind != StationKind.RADIO
    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .padding(contentPadding),
    ) {
        if (showVideo) {
            if (fullscreen) {
                VideoPlaceholder(videoSize)
            } else {
                VideoArea(
                    service = service,
                    videoSize = videoSize,
                    onExpand = { onFullscreenChange(true) },
                )
            }
        }
        if (fullscreen && showVideo) {
            FullscreenVideo(
                service = service,
                videoSize = videoSize,
                onCollapse = { onFullscreenChange(false) },
            )
        }
        if (tabs.size > 1) {
            KindTabRow(
                tabs = tabs,
                selected = selectedFilter,
                onSelect = onFilterChange,
            )
        }
        StationList(
            stations = visibleStations,
            currentStationId = currentStation?.id,
            favoriteIds = favoriteIds,
            selectedFilter = selectedFilter,
            actions = stationActions,
            modifier =
                Modifier
                    .weight(1f)
                    .fillMaxSize(),
        )
    }
}

@Composable
private fun EmptyStationContent(
    onSeedSamples: () -> Unit,
    contentPadding: PaddingValues,
) {
    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .padding(contentPadding)
                .padding(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                stringResource(R.string.no_stations),
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedButton(onClick = onSeedSamples) {
                Text(stringResource(R.string.seed_samples))
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun StationList(
    stations: List<Station>,
    currentStationId: String?,
    favoriteIds: Set<String>,
    selectedFilter: StationFilter,
    actions: PlayerStationActions,
    modifier: Modifier = Modifier,
) {
    val groups = remember(stations) { groupStations(stations) }
    val sectioned = groups.size > 1
    val collapsed = remember { mutableStateMapOf<String, Boolean>() }
    LazyColumn(modifier = modifier) {
        if (!sectioned) {
            items(stations, key = Station::id) { station ->
                StationRow(
                    station = station,
                    isCurrent = station.id == currentStationId,
                    isFavorite = station.id in favoriteIds,
                    actions = actions.forStation(station),
                )
            }
        } else {
            groups.forEach { (group, groupStations) ->
                val key = group ?: NO_GROUP_KEY
                val isCollapsed =
                    collapsed[key] ?: (selectedFilter != StationFilter.FAVORITES)
                stickyHeader(key = "hdr:$key") {
                    GroupHeader(
                        title = group ?: stringResource(R.string.group_ungrouped),
                        count = groupStations.size,
                        collapsed = isCollapsed,
                        onToggle = { collapsed[key] = !isCollapsed },
                    )
                }
                if (!isCollapsed) {
                    items(groupStations, key = Station::id) { station ->
                        StationRow(
                            station = station,
                            isCurrent = station.id == currentStationId,
                            isFavorite = station.id in favoriteIds,
                            actions = actions.forStation(station),
                            showGroupSubtitle = false,
                        )
                    }
                }
            }
        }
    }
}

private data class StationRowActions(
    val onPlay: () -> Unit,
    val onToggleFavorite: () -> Unit,
    val onEdit: () -> Unit,
    val onDelete: () -> Unit,
)

private fun PlayerStationActions.forStation(station: Station): StationRowActions =
    StationRowActions(
        onPlay = { onPlay(station) },
        onToggleFavorite = { onToggleFavorite(station) },
        onEdit = { onEdit(station) },
        onDelete = { onDelete(station) },
    )

@Composable
private fun KindTabRow(
    tabs: List<StationFilter>,
    selected: StationFilter,
    onSelect: (StationFilter) -> Unit,
) {
    val selectedIndex = tabs.indexOf(selected).coerceAtLeast(0)
    TabRow(selectedTabIndex = selectedIndex) {
        tabs.forEach { tab ->
            Tab(
                selected = tab == selected,
                onClick = { onSelect(tab) },
                text = { Text(stringResource(stationFilterLabel(tab))) },
                icon = {
                    stationFilterIcon(tab)?.let { icon ->
                        Icon(
                            icon,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                    }
                },
            )
        }
    }
}

private fun stationFilterLabel(filter: StationFilter): Int =
    when (filter) {
        StationFilter.FAVORITES -> R.string.filter_favorites
        StationFilter.RADIO -> R.string.filter_radio
        StationFilter.TV -> R.string.filter_tv
        StationFilter.OTHER -> R.string.filter_other
    }

private fun stationFilterIcon(filter: StationFilter): ImageVector? =
    when (filter) {
        StationFilter.FAVORITES -> Icons.Filled.Star
        StationFilter.RADIO -> Icons.Filled.Radio
        StationFilter.TV -> Icons.Filled.Tv
        StationFilter.OTHER -> null
    }

private fun kindIcon(kind: StationKind): ImageVector? =
    when (kind) {
        StationKind.TV -> Icons.Filled.Tv
        StationKind.RADIO -> Icons.Filled.Radio
        StationKind.UNKNOWN -> null
    }

@Composable
private fun KindBadge(
    kind: StationKind,
    size: Dp = 16.dp,
) {
    val icon = kindIcon(kind) ?: return
    Icon(
        icon,
        contentDescription =
            stringResource(
                if (kind == StationKind.TV) R.string.filter_tv else R.string.filter_radio,
            ),
        tint = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.size(size),
    )
}

@Composable
private fun VideoSurface(
    service: PlayerService?,
    modifier: Modifier = Modifier,
) {
    val currentService by rememberUpdatedState(service)
    AndroidView(
        modifier = modifier,
        factory = { context ->
            android.view.SurfaceView(context).apply {
                holder.addCallback(
                    object : android.view.SurfaceHolder.Callback {
                        override fun surfaceCreated(holder: android.view.SurfaceHolder) {
                            currentService?.setVideoSurface(holder.surface)
                        }

                        override fun surfaceChanged(
                            holder: android.view.SurfaceHolder,
                            format: Int,
                            width: Int,
                            height: Int,
                        ) = Unit

                        override fun surfaceDestroyed(holder: android.view.SurfaceHolder) {
                            currentService?.setVideoSurface(null)
                        }
                    },
                )
            }
        },
        update = { view ->
            val surface = view.holder.surface
            if (surface != null && surface.isValid) {
                currentService?.setVideoSurface(surface)
            }
        },
    )
    DisposableEffect(service) {
        onDispose { service?.setVideoSurface(null) }
    }
}

@Composable
private fun VideoArea(
    service: PlayerService?,
    videoSize: VideoSize,
    onExpand: () -> Unit,
) {
    val ratio = videoAspectRatio(videoSize)
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .aspectRatio(ratio)
                .background(Color.Black)
                .clickable(onClick = onExpand),
    ) {
        VideoSurface(service = service, modifier = Modifier.fillMaxSize())
        Icon(
            Icons.Filled.Fullscreen,
            contentDescription = stringResource(R.string.video_fullscreen_enter),
            tint = Color.White,
            modifier =
                Modifier
                    .align(Alignment.BottomEnd)
                    .padding(8.dp),
        )
    }
}

@Composable
private fun VideoPlaceholder(videoSize: VideoSize) {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .aspectRatio(videoAspectRatio(videoSize))
                .background(Color.Black),
    )
}

@Composable
private fun FullscreenVideo(
    service: PlayerService?,
    videoSize: VideoSize,
    onCollapse: () -> Unit,
) {
    val context = LocalContext.current
    val activity = remember(context) { context.findActivity() }
    Dialog(
        onDismissRequest = onCollapse,
        properties =
            DialogProperties(
                usePlatformDefaultWidth = false,
                decorFitsSystemWindows = false,
            ),
    ) {
        DisposableEffect(activity) {
            val previousOrientation = activity?.requestedOrientation
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            val window = activity?.window
            val controller = window?.let { WindowInsetsControllerCompat(it, it.decorView) }
            controller?.apply {
                systemBarsBehavior =
                    WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                hide(WindowInsetsCompat.Type.systemBars())
            }
            onDispose {
                controller?.show(WindowInsetsCompat.Type.systemBars())
                activity?.requestedOrientation =
                    previousOrientation ?: ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
            }
        }
        Box(
            modifier =
                Modifier
                    .fillMaxSize()
                    .background(Color.Black)
                    .clickable(onClick = onCollapse),
            contentAlignment = Alignment.Center,
        ) {
            VideoSurface(
                service = service,
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .aspectRatio(videoAspectRatio(videoSize)),
            )
        }
    }
}

private fun videoAspectRatio(videoSize: VideoSize): Float =
    if (videoSize.hasVideo) {
        videoSize.width.toFloat() / videoSize.height
    } else {
        16f / 9f
    }

private fun Context.findActivity(): android.app.Activity? {
    var context: Context? = this
    while (context is android.content.ContextWrapper) {
        if (context is android.app.Activity) return context
        context = context.baseContext
    }
    return null
}

@Composable
private fun StationRow(
    station: Station,
    isCurrent: Boolean,
    isFavorite: Boolean,
    actions: StationRowActions,
    showGroupSubtitle: Boolean = true,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(onClick = actions.onPlay)
                .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        StationLogo(station, size = 44.dp)
        Column(Modifier.weight(1f)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                KindBadge(station.kind)
                Text(
                    station.name,
                    style =
                        if (isCurrent) {
                            MaterialTheme.typography.titleSmall
                        } else {
                            MaterialTheme.typography.bodyLarge
                        },
                    color =
                        if (isCurrent) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurface
                        },
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (showGroupSubtitle && !station.groupTitle.isNullOrBlank()) {
                Text(
                    station.groupTitle,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        IconButton(onClick = actions.onToggleFavorite) {
            Icon(
                if (isFavorite) Icons.Filled.Star else Icons.Filled.StarBorder,
                contentDescription =
                    stringResource(
                        if (isFavorite) {
                            R.string.remove_station_favorite
                        } else {
                            R.string.add_station_favorite
                        },
                    ),
            )
        }
        IconButton(onClick = actions.onEdit) {
            Icon(
                Icons.Filled.Edit,
                contentDescription = stringResource(R.string.edit_station),
            )
        }
        IconButton(onClick = actions.onDelete) {
            Icon(
                Icons.Filled.Delete,
                contentDescription = stringResource(R.string.delete_station),
            )
        }
    }
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
            contentDescription =
                stringResource(
                    if (collapsed) R.string.group_expand else R.string.group_collapse,
                ),
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

@Composable
internal fun StationLogo(
    station: Station,
    size: Dp,
) {
    val fallback = painterResource(R.drawable.ic_radio_fallback)
    val chain = remember(station.logoUrl, station.streamUrl) { Favicons.logoChain(station) }
    var step by remember(station.logoUrl, station.streamUrl) { mutableStateOf(0) }
    Box(
        modifier =
            Modifier
                .size(size)
                .clip(androidx.compose.foundation.shape.RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        AsyncImage(
            model = chain.getOrNull(step),
            contentDescription = null,
            onError = { if (step < chain.size) step += 1 },
            error = fallback,
            fallback = fallback,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop,
        )
    }
}

private const val NO_GROUP_KEY = "\u0000ungrouped"
