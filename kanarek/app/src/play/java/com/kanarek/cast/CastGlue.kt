@file:androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)

package com.kanarek.cast

import android.content.Context
import android.net.Uri
import androidx.media3.cast.CastPlayer
import androidx.media3.cast.MediaItemConverter
import androidx.media3.cast.SessionAvailabilityListener
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import com.google.android.gms.cast.MediaInfo
import com.google.android.gms.cast.MediaQueueItem
import com.google.android.gms.cast.framework.CastContext
import com.google.android.gms.common.images.WebImage
import org.json.JSONObject

/**
 * Play-flavor Google Cast support. The foss flavor ships a no-op twin of this object with the
 * same public surface, so main-source code (PlayerService, PlayerScreen) can reference it
 * unconditionally without any Play Services dependency leaking into the FOSS build.
 *
 * The receiver is Google's Default Media Receiver — it fetches the stream itself, on the cast
 * device, so per-stream User-Agent/Referer spoofing (kanarek's streamHeaders side-table) does
 * NOT apply while casting. Geo/hotlink-locked streams that need those headers will play locally
 * but may fail on the cast target; that's a receiver-side limitation, not a bug here.
 */
object CastGlue {
    const val AVAILABLE: Boolean = true

    /**
     * Builds the app's single [CastPlayer], or null when Google Play services / the Cast module
     * is unavailable on this device (the app then behaves exactly like the foss flavor).
     * [onAvailability] is invoked with the cast player when a cast session (re)connects and with
     * null when it ends — including immediately, if a session already exists when this is called.
     */
    fun createCastPlayer(
        context: Context,
        onAvailability: (Player?) -> Unit,
    ): Player? =
        try {
            val castContext = CastContext.getSharedInstance(context.applicationContext)
            val player = CastPlayer(castContext, KanarekMediaItemConverter())
            player.setSessionAvailabilityListener(
                object : SessionAvailabilityListener {
                    override fun onCastSessionAvailable() = onAvailability(player)

                    override fun onCastSessionUnavailable() = onAvailability(null)
                },
            )
            if (player.isCastSessionAvailable) onAvailability(player)
            player
        } catch (_: Exception) {
            null
        }

    fun releaseCastPlayer(player: Player?) {
        (player as? CastPlayer)?.let {
            it.setSessionAvailabilityListener(null)
            it.release()
        }
    }
}

/**
 * Kanarek's own converter instead of [androidx.media3.cast.DefaultMediaItemConverter], because
 * the default one requires `MediaItem.mimeType` to be set — and kanarek's items deliberately
 * carry none (a wrong hint would break local ExoPlayer source selection for bare Icecast URLs).
 * Content type is guessed from the URL here, receiver-side only; everything is a live stream.
 */
internal class KanarekMediaItemConverter : MediaItemConverter {
    override fun toMediaQueueItem(mediaItem: MediaItem): MediaQueueItem {
        val url = requireNotNull(mediaItem.localConfiguration).uri.toString()
        val metadata =
            com.google.android.gms.cast
                .MediaMetadata(com.google.android.gms.cast.MediaMetadata.MEDIA_TYPE_GENERIC)
        val title = mediaItem.mediaMetadata.title?.toString()
        val artist = mediaItem.mediaMetadata.artist?.toString()
        title?.let { metadata.putString(com.google.android.gms.cast.MediaMetadata.KEY_TITLE, it) }
        artist?.let { metadata.putString(com.google.android.gms.cast.MediaMetadata.KEY_SUBTITLE, it) }
        val artwork = mediaItem.mediaMetadata.artworkUri
        artwork?.let { metadata.addImage(WebImage(it)) }
        // Round-trip payload for toMediaItem — the receiver echoes customData back verbatim.
        val custom =
            JSONObject()
                .put(KEY_MEDIA_ID, mediaItem.mediaId)
                .put(KEY_URI, url)
                .apply {
                    title?.let { put(KEY_TITLE, it) }
                    artist?.let { put(KEY_ARTIST, it) }
                    artwork?.let { put(KEY_ARTWORK, it.toString()) }
                }
        val info =
            MediaInfo
                .Builder(url)
                .setStreamType(MediaInfo.STREAM_TYPE_LIVE)
                .setContentType(guessContentType(url))
                .setMetadata(metadata)
                .setCustomData(custom)
                .build()
        return MediaQueueItem.Builder(info).build()
    }

    override fun toMediaItem(mediaQueueItem: MediaQueueItem): MediaItem {
        val info = mediaQueueItem.media
        val custom = info?.customData
        val uri = custom?.optString(KEY_URI)?.takeIf { it.isNotEmpty() } ?: info?.contentId.orEmpty()
        return MediaItem
            .Builder()
            .setMediaId(custom?.optString(KEY_MEDIA_ID)?.takeIf { it.isNotEmpty() } ?: uri)
            .setUri(uri)
            .setMediaMetadata(
                MediaMetadata
                    .Builder()
                    .setTitle(custom?.optString(KEY_TITLE)?.takeIf { it.isNotEmpty() })
                    .setArtist(custom?.optString(KEY_ARTIST)?.takeIf { it.isNotEmpty() })
                    .setArtworkUri(
                        custom?.optString(KEY_ARTWORK)?.takeIf { it.isNotEmpty() }?.let(Uri::parse),
                    ).build(),
            ).build()
    }

    private fun guessContentType(url: String): String {
        val path = Uri.parse(url).path.orEmpty().lowercase()
        return when {
            path.endsWith(".m3u8") || path.endsWith(".m3u") -> "application/x-mpegurl"
            path.endsWith(".mpd") -> "application/dash+xml"
            path.endsWith(".mp4") || path.endsWith(".m4v") -> "video/mp4"
            path.endsWith(".ts") -> "video/mp2t"
            path.endsWith(".aac") -> "audio/aac"
            path.endsWith(".ogg") || path.endsWith(".opus") -> "audio/ogg"
            path.endsWith(".flac") -> "audio/flac"
            path.endsWith(".m4a") -> "audio/mp4"
            // Bare Icecast/SHOUTcast mounts (most radio streams) are MP3 far more often than not.
            else -> "audio/mpeg"
        }
    }

    private companion object {
        const val KEY_MEDIA_ID = "mediaId"
        const val KEY_URI = "uri"
        const val KEY_TITLE = "title"
        const val KEY_ARTIST = "artist"
        const val KEY_ARTWORK = "artworkUri"
    }
}
