package com.kanarek.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Radio
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarBorder
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material3.BottomAppBar
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.kanarek.R
import com.kanarek.data.Favicons
import com.kanarek.data.Station
import com.kanarek.data.StationKind
import com.kanarek.player.PlayerUiState
import com.kanarek.player.RadioParadiseMetadata
import com.kanarek.player.fetchRadioParadiseMetadata
import com.kanarek.player.radioParadiseChannel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

@Composable
internal fun RichPlayerBottomControls(
    station: Station,
    playerState: PlayerUiState,
    isFavorite: Boolean,
    actions: PlayerControlActions,
) {
    val metadata by rememberRadioParadiseMetadata(station, playerState)
    BottomAppBar {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            PlayerIdentity(station, metadata, playerState.nowPlaying)
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceEvenly,
            ) {
                PlayerControlButtons(playerState, isFavorite, actions)
            }
        }
    }
}

@Composable
private fun rememberRadioParadiseMetadata(
    station: Station,
    playerState: PlayerUiState,
): State<RadioParadiseMetadata?> {
    val playbackActive = playerState.isPlaying || playerState.isBuffering
    return produceState(
        initialValue = null,
        key1 = station.streamUrl,
        key2 = playbackActive,
    ) {
        val channel = radioParadiseChannel(station.streamUrl) ?: return@produceState
        if (!playbackActive) return@produceState
        while (true) {
            val result =
                withContext(Dispatchers.IO) {
                    runCatching { fetchRadioParadiseMetadata(channel) }.getOrNull()
                }
            if (result != null) value = result
            delay(result?.refreshAfterMillis ?: METADATA_RETRY_MS)
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun PlayerIdentity(
    station: Station,
    metadata: RadioParadiseMetadata?,
    nowPlaying: String?,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        RichStationLogo(
            station = station,
            artworkUrl = metadata?.artworkUrl,
            size = 64.dp,
        )
        Column(Modifier.weight(1f)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                RichKindBadge(station.kind, size = 14.dp)
                Text(
                    station.name,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            val trackTitle =
                metadata?.title?.takeIf(String::isNotBlank)
                    ?: nowPlaying?.takeIf(String::isNotBlank)
                    ?: station.groupTitle?.takeIf(String::isNotBlank)
            if (trackTitle != null) {
                Text(
                    trackTitle,
                    modifier = Modifier.basicMarquee(),
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Clip,
                    softWrap = false,
                )
            }

            val details =
                listOfNotNull(
                    metadata?.artist?.takeIf(String::isNotBlank),
                    metadata?.album?.takeIf(String::isNotBlank),
                ).distinct().joinToString(" · ")
            if (details.isNotBlank()) {
                Text(
                    details,
                    modifier = Modifier.basicMarquee(),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Clip,
                    softWrap = false,
                )
            }
        }
    }
}

@Composable
private fun PlayerControlButtons(
    playerState: PlayerUiState,
    isFavorite: Boolean,
    actions: PlayerControlActions,
) {
    IconButton(onClick = actions.onToggleFavorite) {
        Icon(
            if (isFavorite) Icons.Filled.Star else Icons.Filled.StarBorder,
            contentDescription =
                stringResource(
                    if (isFavorite) R.string.remove_station_favorite else R.string.add_station_favorite,
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
                    if (playerState.isPlaying) R.string.action_pause else R.string.action_play,
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

@Composable
private fun RichStationLogo(
    station: Station,
    artworkUrl: String?,
    size: Dp,
) {
    val fallback = painterResource(R.drawable.ic_radio_fallback)
    val chain =
        remember(artworkUrl, station.logoUrl, station.streamUrl) {
            buildList {
                artworkUrl?.takeIf(String::isNotBlank)?.let(::add)
                Favicons.logoChain(station).forEach { candidate ->
                    if (candidate !in this) add(candidate)
                }
            }
        }
    var step by remember(artworkUrl, station.logoUrl, station.streamUrl) { mutableIntStateOf(0) }
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

@Composable
private fun RichKindBadge(
    kind: StationKind,
    size: Dp,
) {
    val icon =
        when (kind) {
            StationKind.TV -> Icons.Filled.Tv
            StationKind.RADIO -> Icons.Filled.Radio
            StationKind.UNKNOWN -> return
        }
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

private const val METADATA_RETRY_MS = 45_000L
