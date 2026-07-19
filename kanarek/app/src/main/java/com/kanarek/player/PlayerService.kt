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
import com.kanarek.data.SettingsStore
import com.kanarek.data.Station
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
        session = MediaSession.Builder(this, player).build()

        player.addListener(
            object : Player.Listener {
                override fun onIsPlayingChanged(isPlaying: Boolean) = pushState()

                override fun onPlaybackStateChanged(playbackState: Int) = pushState()

                override fun onMediaItemTransition(
                    mediaItem: MediaItem?,
                    reason: Int,
                ) {
                    // New station — drop the previous stream's ICY title before pushing state,
                    // otherwise the old track name flashes under the new station's name.
                    _uiState.value = _uiState.value.copy(nowPlaying = null)
                    pushState()
                    mediaItem?.mediaId?.let { id -> scope.launch { settings.setLastStationId(id) } }
                }

                // ICY in-stream metadata (SHOUTcast/Icecast "StreamTitle") — how internet radios
                // announce the playing track. Read from the timed-metadata event directly rather
                // than the merged Player.mediaMetadata, so our own MediaItem title (the station
                // name) and the stream's track title never fight over the same field.
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
            },
        )

        // Restore the last playlist so the widget has something to show before the app is ever
        // opened, and tapping play resumes where it left off — without starting playback yet.
        scope.launch {
            val stations = settings.stationsNow()
            if (stations.isNotEmpty()) {
                setPlaylistInternal(stations, startId = settings.lastStationIdNow(), autoplay = false)
            }
        }
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession = session

    override fun onBind(intent: Intent): IBinder? = if (intent.action == SERVICE_INTERFACE) super.onBind(intent) else binder

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

    /** Called by the UI whenever the persisted station list changes (add/edit/delete/import).
     *  Editing the list must not silence a playing stream: if the currently playing station
     *  survives the edit, playback continues on it; only when it was deleted (or nothing was
     *  playing) does the playlist land at rest. */
    fun setPlaylist(stations: List<Station>) {
        val currentId = if (player.mediaItemCount > 0) player.currentMediaItem?.mediaId else null
        val wasPlaying = player.playWhenReady
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
        if (player.mediaItemCount == 0) {
            scope.launch { setPlaylistInternal(settings.stationsNow(), startId = settings.lastStationIdNow(), autoplay = true) }
            return
        }
        player.playWhenReady = !player.playWhenReady
    }

    fun next() {
        if (player.mediaItemCount > 0) player.seekToNextMediaItem()
    }

    fun previous() {
        if (player.mediaItemCount > 0) player.seekToPreviousMediaItem()
    }

    /** Attach (or detach, with null) the Activity's video output. Plain [android.view.Surface] so
     *  the service's public surface stays free of unstable Media3 types. The Activity owns the
     *  surface lifecycle (a [android.view.SurfaceView]); we just forward it to the one player. */
    fun setVideoSurface(surface: android.view.Surface?) {
        player.setVideoSurface(surface)
    }

    private fun setPlaylistInternal(
        stations: List<Station>,
        startId: String?,
        autoplay: Boolean,
    ) {
        if (stations.isEmpty()) {
            // Deleting the last station stops and clears playback; without this the old
            // playlist kept playing with no station left in the UI to control it.
            player.stop()
            player.clearMediaItems()
            streamHeaders.clear()
            _videoSize.value = VideoSize()
            _uiState.value = PlayerUiState()
            pushWidget()
            return
        }
        _videoSize.value = VideoSize()
        streamHeaders.clear()
        stations.forEach { s ->
            val headers =
                buildMap {
                    s.userAgent?.takeIf { it.isNotBlank() }?.let { put("User-Agent", it) }
                    s.referrer?.takeIf { it.isNotBlank() }?.let { put("Referer", it) }
                }
            if (headers.isNotEmpty()) streamHeaders[s.streamUrl] = headers
        }
        val items = stations.map { it.toMediaItem() }
        val startIndex = stations.indexOfFirst { it.id == startId }.let { if (it >= 0) it else 0 }
        player.setMediaItems(items, startIndex, C.TIME_UNSET)
        player.prepare()
        player.playWhenReady = autoplay
        _uiState.value = PlayerUiState(stations = stations, currentIndex = startIndex, isPlaying = autoplay)
        pushWidget()
    }

    private fun pushState() {
        _uiState.value =
            _uiState.value.copy(
                currentIndex = player.currentMediaItemIndex,
                isPlaying = player.isPlaying,
                isBuffering = player.playbackState == Player.STATE_BUFFERING,
            )
        pushWidget()
    }

    /** Renders from the on-disk image cache only (no network) — the fetch itself runs in
     *  [prefetchLogo], kicked off below whenever the current station changes. */
    private fun pushWidget() {
        val state = _uiState.value
        // Off the main thread: the widget render reads (and decodes) the logo bitmap from the
        // on-disk cache, and playback-state callbacks can arrive in rapid bursts on a flaky
        // live stream — doing that disk I/O + RemoteViews push inline on main was an ANR risk.
        scope.launch(Dispatchers.Default) { pushWidgetBlocking(state) }
    }

    private fun pushWidgetBlocking(state: PlayerUiState) {
        // A station with no logo of its own borrows its stream host's favicon (see Favicons) so
        // the widget shows *something* branded instead of the generic glyph. Best-effort only —
        // on fetch failure the widget's drawable fallback still applies.
        val station =
            state.currentStation?.let { s ->
                if (s.logoUrl.isNullOrBlank()) {
                    com.kanarek.data.Favicons
                        .firstFor(s.streamUrl)
                        ?.let { s.copy(logoUrl = it) } ?: s
                } else {
                    s
                }
            }
        prefetchLogo(station?.logoUrl)
        PlayerWidgetProvider.updateAll(applicationContext, station, state.isPlaying)
    }

    /** Warms the shared widget image cache for the current station's logo, off the main thread,
     *  then re-pushes the widget once it lands (a cache miss on the first push just shows the
     *  fallback glyph until this completes). */
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
                // Re-push through pushWidget (not updateAll directly) so the favicon-fallback
                // logo substitution above is applied to this refresh too. No loop: the second
                // pass finds the image cached and skips this branch.
                pushWidget()
            }
        }
    }

    override fun onDestroy() {
        session.release()
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

        /** Same shape as NewsRemoteViewsService's image fetch, writing straight into the shared
         *  [com.kanarek.widget.WidgetImageCache] rather than returning a bitmap. */
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
                    val bytes = conn.inputStream.use { it.readBytes() }
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
            var w = bounds.outWidth
            var h = bounds.outHeight
            while (w / 2 >= maxPx || h / 2 >= maxPx) {
                w /= 2
                h /= 2
                sample *= 2
            }
            val opts =
                android.graphics.BitmapFactory
                    .Options()
                    .apply { inSampleSize = sample }
            return android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
        }
    }
}
