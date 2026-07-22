@file:androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)

package com.kanarek.player

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Binder
import android.os.IBinder
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import com.kanarek.cast.CastGlue
import com.kanarek.data.SettingsStore
import com.kanarek.data.Station
import com.kanarek.data.readBytesCapped
import com.kanarek.widget.PlayerWidgetProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.net.HttpURLConnection
import java.net.URL

/** Snapshot the Activity/widget read to render the current playlist position. */
data class PlayerUiState(
    val stations: List<Station> = emptyList(),
    val currentIndex: Int = -1,
    val isPlaying: Boolean = false,
    val isBuffering: Boolean = false,
    /** In-stream "now playing" text (ICY StreamTitle) for the current station — the track/show
     *  an internet radio announces mid-stream. Null when the stream carries none (typical for
     *  TV) or between stations; cleared on every station change so a stale title never lingers. */
    val nowPlaying: String? = null,
) {
    val currentStation: Station? get() = stations.getOrNull(currentIndex)
}

/** Current decoded video dimensions, pushed to the Activity so it can size the video surface to
 *  the stream's aspect ratio. [width]/[height] are 0 when the current stream carries no video
 *  (a radio station), which the UI reads as "hide the surface, this is audio-only". */
data class VideoSize(
    val width: Int = 0,
    val height: Int = 0,
) {
    val hasVideo: Boolean get() = width > 0 && height > 0
}

/**
 * Background playback engine: one [ExoPlayer] + [MediaSession] for the whole app, so playback
 * (and the system media notification / lock-screen controls that come with a MediaSession) keeps
 * running independent of any Activity. The player UI (`PlayerScreen`, hosted by
 * [com.kanarek.HomeActivity]) binds to this directly —
 * same process, so a plain [Binder] is enough, no MediaController/SessionToken round-trip needed.
 * The home-screen widget can't hold a live binder, so it drives playback through simple service
 * actions instead (see [PlayerWidgetProvider]); this service pushes the resulting state back out
 * to every widget instance via [PlayerWidgetProvider.updateAll].
 *
 * Not annotated `@UnstableApi` itself — that would make every external reference to this class
 * (Activity, widget) require its own opt-in too. The file-level opt-in above covers the unstable
 * Media3 calls made *inside* this file only; PlayerService's own public surface (LocalBinder,
 * uiState, setPlaylist, next, previous, togglePlayPause) is plain Kotlin/our own types.
 */
class PlayerService : MediaSessionService() {
    private lateinit var player: ExoPlayer

    /** The play flavor's CastPlayer (null in foss or when Play services are missing). Lives for
     *  the whole service lifetime; [activePlayer] flips between it and the local [player] as cast
     *  sessions come and go. */
    private var castPlayer: Player? = null

    /** Whichever engine currently owns playback — the local ExoPlayer or the CastPlayer. Every
     *  control path (toggle/next/prev/setPlaylist/pushState) goes through this, never [player]
     *  directly; only the video surface stays pinned to the local player (cast has no surface). */
    private lateinit var activePlayer: Player
    private lateinit var session: MediaSession
    private lateinit var settings: SettingsStore
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private val _uiState = MutableStateFlow(PlayerUiState())
    val uiState: StateFlow<PlayerUiState> = _uiState.asStateFlow()

    /** Decoded video dimensions of the current stream (0×0 for audio), so the player UI
     *  can show and aspect-size a video surface for TV and hide it for radio. */
    private val _videoSize = MutableStateFlow(VideoSize())
    val videoSize: StateFlow<VideoSize> = _videoSize.asStateFlow()

    /** Per-URL HTTP headers (User-Agent/Referer) for streams that need spoofed headers to pass
     *  geo/hotlink checks — keyed by [Station.streamUrl], repopulated on every [setPlaylistInternal]
     *  and read back by the [ResolvingDataSource] wired into the player in [onCreate]. Media3's
     *  [MediaItem] has no per-item request-headers field of its own, so this side-table plus a
     *  resolver keyed on the request URI is the standard way to get there. */
    private val streamHeaders = mutableMapOf<String, Map<String, String>>()

    private lateinit var playerListener: Player.Listener

    private val binder = LocalBinder()

    inner class LocalBinder : Binder() {
        val service: PlayerService get() = this@PlayerService
    }

    override fun onCreate() {
        super.onCreate()
        settings = SettingsStore(applicationContext)

        val httpDataSourceFactory =
            DefaultHttpDataSource
                .Factory()
                .setUserAgent("kanarek/1.0 (Android)")
                .setAllowCrossProtocolRedirects(true)
        val dataSourceFactory: DataSource.Factory =
            ResolvingDataSource.Factory(httpDataSourceFactory) { dataSpec ->
                val headers = streamHeaders[dataSpec.uri.toString()]
                if (headers.isNullOrEmpty()) dataSpec else dataSpec.buildUpon().setHttpRequestHeaders(headers).build()
            }

        player =
            ExoPlayer
                .Builder(applicationContext)
                .setMediaSourceFactory(DefaultMediaSourceFactory(dataSourceFactory))
                .build()
                .apply {
                    setAudioAttributes(
                        AudioAttributes
                            .Builder()
                            .setUsage(C.USAGE_MEDIA)
                            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                            .build(),
                        // handleAudioFocus =
                        true,
                    )
                    setHandleAudioBecomingNoisy(true)
                }
        activePlayer = player
        session = MediaSession.Builder(this, player).build()

        playerListener =
            object : Player.Listener {
                override fun onIsPlayingChanged(isPlaying: Boolean) = pushState()

                override fun onPlaybackStateChanged(playbackState: Int) = pushState()

                override fun onMediaItemTransition(
                    mediaItem: MediaItem?,
                    reason: Int,
                ) {
                    _uiState.value = _uiState.value.copy(nowPlaying = null)
                    pushState()
                    mediaItem?.mediaId?.let { id -> scope.launch { settings.setLastStationId(id) } }
                }

                override fun onMetadata(metadata: androidx.media3.common.Metadata) {
                    for (i in 0 until metadata.length()) {
                        val entry = metadata.get(i)
                        if (entry is androidx.media3.extractor.metadata.icy.IcyInfo) {
                            val title = entry.title?.trim()?.takeIf { it.isNotEmpty() }
                            if (_uiState.value.nowPlaying != title) {
                                _uiState.value = _uiState.value.copy(nowPlaying = title)
                                pushWidget()
                            }
                            return
                        }
                    }
                }

                override fun onPlayerError(error: androidx.media3.common.PlaybackException) = pushState()

                override fun onVideoSizeChanged(size: androidx.media3.common.VideoSize) {
                    _videoSize.value = VideoSize(size.width, size.height)
                }
            }
        activePlayer.addListener(playerListener)

        castPlayer =
            CastGlue.createCastPlayer(applicationContext) { cast ->
                switchTo(cast ?: player)
            }

        scope.launch {
            val stations = settings.stationsNow()
            if (stations.isNotEmpty()) {
                setPlaylistInternal(stations, startId = settings.lastStationIdNow(), autoplay = false)
            }
        }
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession = session

    override fun onBind(intent: Intent): IBinder? = if (intent.action == SERVICE_INTERFACE) super.onBind(intent) else binder

    override fun onUnbind(intent: Intent): Boolean {
        // The Compose client binds without SERVICE_INTERFACE. Clear its output when that UI leaves,
        // but do not let transient SurfaceView destruction during inline/fullscreen hand-off clear a
        // newer surface that may already have been attached.
        if (intent.action != SERVICE_INTERFACE && this::player.isInitialized) player.clearVideoSurface()
        return super.onUnbind(intent)
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int,
    ): Int {
        when (intent?.action) {
            ACTION_TOGGLE -> togglePlayPause()
            ACTION_NEXT -> next()
            ACTION_PREV -> previous()
        }
        return super.onStartCommand(intent, flags, startId)
    }

    fun setPlaylist(stations: List<Station>) {
        val currentId = if (activePlayer.mediaItemCount > 0) activePlayer.currentMediaItem?.mediaId else null
        val wasPlaying = activePlayer.playWhenReady
        scope.launch {
            val keepId = currentId?.takeIf { id -> stations.any { it.id == id } }
            setPlaylistInternal(
                stations,
                startId = keepId ?: settings.lastStationIdNow(),
                autoplay = wasPlaying && keepId != null,
            )
        }
    }

    fun playStationById(id: String) {
        scope.launch { setPlaylistInternal(settings.stationsNow(), startId = id, autoplay = true) }
    }

    fun togglePlayPause() {
        if (activePlayer.mediaItemCount == 0) {
            scope.launch { setPlaylistInternal(settings.stationsNow(), startId = settings.lastStationIdNow(), autoplay = true) }
            return
        }
        activePlayer.playWhenReady = !activePlayer.playWhenReady
    }

    fun next() {
        if (activePlayer.mediaItemCount > 0) activePlayer.seekToNextMediaItem()
    }

    fun previous() {
        if (activePlayer.mediaItemCount > 0) activePlayer.seekToPreviousMediaItem()
    }

    /** Attach the Activity's current video output. Null detach requests from a destroyed
     *  SurfaceView are ignored because they can race with a newly attached fullscreen/inline
     *  surface. The local UI binding clears the output definitively in [onUnbind]. */
    fun setVideoSurface(surface: android.view.Surface?) {
        if (surface != null && surface.isValid) player.setVideoSurface(surface)
    }

    private fun setPlaylistInternal(
        stations: List<Station>,
        startId: String?,
        autoplay: Boolean,
    ) {
        if (stations.isEmpty()) {
            activePlayer.stop()
            activePlayer.clearMediaItems()
            streamHeaders.clear()
            _videoSize.value = VideoSize()
            _uiState.value = PlayerUiState()
            pushWidget()
            return
        }
        _videoSize.value = VideoSize()
        streamHeaders.clear()
        stations.forEach { station ->
            val headers =
                buildMap {
                    station.userAgent?.takeIf { it.isNotBlank() }?.let { put("User-Agent", it) }
                    station.referrer?.takeIf { it.isNotBlank() }?.let { put("Referer", it) }
                }
            if (headers.isNotEmpty()) streamHeaders[station.streamUrl] = headers
        }
        val items = stations.map { it.toMediaItem() }
        val startIndex = stations.indexOfFirst { it.id == startId }.let { if (it >= 0) it else 0 }
        activePlayer.setMediaItems(items, startIndex, C.TIME_UNSET)
        activePlayer.prepare()
        activePlayer.playWhenReady = autoplay
        _uiState.value = PlayerUiState(stations = stations, currentIndex = startIndex, isPlaying = autoplay)
        pushWidget()
    }

    private fun switchTo(target: Player) {
        if (!this::activePlayer.isInitialized || target === activePlayer) return
        val old = activePlayer
        val wasPlaying = old.playWhenReady
        val index = if (old.mediaItemCount > 0) old.currentMediaItemIndex else _uiState.value.currentIndex.coerceAtLeast(0)
        old.removeListener(playerListener)
        old.stop()
        activePlayer = target
        target.addListener(playerListener)
        session.player = target
        _videoSize.value = VideoSize()
        val stations = _uiState.value.stations
        if (target.mediaItemCount == 0 && stations.isNotEmpty()) {
            target.setMediaItems(stations.map { it.toMediaItem() }, index, C.TIME_UNSET)
            target.prepare()
            target.playWhenReady = wasPlaying
        }
        pushState()
    }

    private fun pushState() {
        _uiState.value =
            _uiState.value.copy(
                currentIndex = activePlayer.currentMediaItemIndex,
                isPlaying = activePlayer.isPlaying,
                isBuffering = activePlayer.playbackState == Player.STATE_BUFFERING,
            )
        pushWidget()
    }

    private fun pushWidget() {
        val state = _uiState.value
        val station =
            state.currentStation?.let { current ->
                if (current.logoUrl.isNullOrBlank()) {
                    com.kanarek.data.Favicons
                        .firstFor(current.streamUrl)
                        ?.let { current.copy(logoUrl = it) } ?: current
                } else {
                    current
                }
            }
        prefetchLogo(station?.logoUrl)
        PlayerWidgetProvider.updateAll(applicationContext, station, state.isPlaying)
    }

    private fun prefetchLogo(url: String?) {
        if (url.isNullOrBlank()) return
        scope.launch(Dispatchers.IO) {
            val cached =
                runCatching {
                    com.kanarek.widget.WidgetImageCache
                        .get(applicationContext, url)
                }.getOrNull()
            if (cached == null) {
                fetchAndCacheBitmap(applicationContext, url)
                pushWidget()
            }
        }
    }

    override fun onDestroy() {
        session.release()
        CastGlue.releaseCastPlayer(castPlayer)
        player.release()
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        const val ACTION_TOGGLE = "com.kanarek.player.action.TOGGLE"
        const val ACTION_NEXT = "com.kanarek.player.action.NEXT"
        const val ACTION_PREV = "com.kanarek.player.action.PREV"

        private const val IMG_TIMEOUT_MS = 6_000
        private const val MAX_IMAGE_PX = 200
        private const val MAX_IMAGE_BYTES = 3 * 1024 * 1024

        private fun Station.toMediaItem(): MediaItem =
            MediaItem
                .Builder()
                .setMediaId(id)
                .setUri(streamUrl)
                .setMediaMetadata(
                    MediaMetadata
                        .Builder()
                        .setTitle(name)
                        .setArtist(groupTitle)
                        .setArtworkUri(logoUrl?.takeIf { it.isNotBlank() }?.let { Uri.parse(it) })
                        .build(),
                ).build()

        private fun fetchAndCacheBitmap(
            context: Context,
            url: String,
        ) {
            runCatching {
                val conn =
                    (URL(url).openConnection() as HttpURLConnection).apply {
                        connectTimeout = IMG_TIMEOUT_MS
                        readTimeout = IMG_TIMEOUT_MS
                        instanceFollowRedirects = true
                    }
                try {
                    if (conn.responseCode !in 200..299) return
                    val bytes = conn.inputStream.use { it.readBytesCapped(MAX_IMAGE_BYTES) }
                    decodeScaled(bytes, MAX_IMAGE_PX)?.let {
                        com.kanarek.widget.WidgetImageCache
                            .put(context, url, it)
                    }
                } finally {
                    conn.disconnect()
                }
            }
        }

        private fun decodeScaled(
            bytes: ByteArray,
            maxPx: Int,
        ): android.graphics.Bitmap? {
            val bounds =
                android.graphics.BitmapFactory
                    .Options()
                    .apply { inJustDecodeBounds = true }
            android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            var sample = 1
            var width = bounds.outWidth
            var height = bounds.outHeight
            while (width / 2 >= maxPx || height / 2 >= maxPx) {
                width /= 2
                height /= 2
                sample *= 2
            }
            val options =
                android.graphics.BitmapFactory
                    .Options()
                    .apply { inSampleSize = sample }
            return android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
        }
    }
}
