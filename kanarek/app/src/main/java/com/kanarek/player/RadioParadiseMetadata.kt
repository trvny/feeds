package com.kanarek.player

import com.kanarek.data.readBytesCapped
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

internal data class RadioTrackMetadata(
    val title: String,
    val artist: String,
    val album: String?,
    val artworkUrl: String?,
    val refreshAfterMillis: Long,
) {
    val displayText: String
        get() = listOf(artist, title).filter(String::isNotBlank).joinToString(" — ")
}

internal fun radioParadiseChannel(streamUrl: String): Int? {
    val uri = runCatching { URI(streamUrl) }.getOrNull() ?: return null
    if (uri.scheme !in setOf("http", "https")) return null
    val host = uri.host?.lowercase() ?: return null
    if (host != RADIO_PARADISE_HOST && !host.endsWith(".$RADIO_PARADISE_HOST")) return null

    val path = uri.path.orEmpty().lowercase()
    return when {
        "rock" in path -> 2
        "global" in path || "world" in path -> 3
        "mellow" in path || path.endsWith("/ogg-192m") -> 1
        else -> 0
    }
}

internal fun parseRadioParadiseMetadata(json: String): RadioTrackMetadata? {
    val title = jsonString(json, "title").orEmpty().trim()
    val artist = jsonString(json, "artist").orEmpty().trim()
    if (title.isEmpty() && artist.isEmpty()) return null

    val seconds = jsonNumber(json, "time")?.toDoubleOrNull()?.toLong() ?: DEFAULT_REFRESH_SECONDS
    return RadioTrackMetadata(
        title = title,
        artist = artist,
        album = jsonString(json, "album")?.trim()?.takeIf(String::isNotEmpty),
        artworkUrl =
            sequenceOf("cover_med", "cover", "cover_small")
                .mapNotNull { jsonString(json, it) }
                .mapNotNull(::safeRadioParadiseArtworkUrl)
                .firstOrNull(),
        refreshAfterMillis =
            (seconds + REFRESH_GRACE_SECONDS)
                .coerceIn(MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS) * 1_000,
    )
}

internal fun fetchRadioParadiseMetadata(channel: Int): RadioTrackMetadata? {
    if (channel !in 0..3) return null
    val connection =
        (URL("$RADIO_PARADISE_API?chan=$channel").openConnection() as HttpURLConnection).apply {
            connectTimeout = HTTP_TIMEOUT_MS
            readTimeout = HTTP_TIMEOUT_MS
            instanceFollowRedirects = false
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "kanarek/1.0 (Android)")
        }
    return try {
        if (connection.responseCode !in 200..299) return null
        val json =
            connection.inputStream.use { input ->
                input.readBytesCapped(MAX_METADATA_BYTES).toString(Charsets.UTF_8)
            }
        parseRadioParadiseMetadata(json)
    } finally {
        connection.disconnect()
    }
}

private fun jsonString(
    json: String,
    key: String,
): String? {
    val pattern = Regex("\\\"${Regex.escape(key)}\\\"\\s*:\\s*\\\"((?:\\\\.|[^\\\"\\\\])*)\\\"")
    val encoded = pattern.find(json)?.groupValues?.get(1) ?: return null
    return decodeJsonString(encoded)
}

private fun jsonNumber(
    json: String,
    key: String,
): String? =
    Regex("\\\"${Regex.escape(key)}\\\"\\s*:\\s*\\\"?(-?\\d+(?:\\.\\d+)?)")
        .find(json)
        ?.groupValues
        ?.get(1)

private fun decodeJsonString(encoded: String): String? {
    val output = StringBuilder(encoded.length)
    var index = 0
    while (index < encoded.length) {
        val current = encoded[index++]
        if (current != '\\') {
            output.append(current)
            continue
        }
        if (index >= encoded.length) return null
        when (val escaped = encoded[index++]) {
            '\"', '\\', '/' -> output.append(escaped)
            'b' -> output.append('\b')
            'f' -> output.append('\u000C')
            'n' -> output.append('\n')
            'r' -> output.append('\r')
            't' -> output.append('\t')
            'u' -> {
                if (index + 4 > encoded.length) return null
                val codePoint = encoded.substring(index, index + 4).toIntOrNull(16) ?: return null
                output.append(codePoint.toChar())
                index += 4
            }
            else -> return null
        }
    }
    return output.toString()
}

private fun safeRadioParadiseArtworkUrl(value: String): String? {
    val uri = runCatching { URI(value.trim()) }.getOrNull() ?: return null
    if (uri.scheme != "https" || uri.userInfo != null) return null
    val host = uri.host?.lowercase() ?: return null
    return value.takeIf {
        host == RADIO_PARADISE_HOST || host.endsWith(".$RADIO_PARADISE_HOST")
    }
}

private const val RADIO_PARADISE_HOST = "radioparadise.com"
private const val RADIO_PARADISE_API = "https://api.radioparadise.com/api/now_playing"
private const val HTTP_TIMEOUT_MS = 6_000
private const val MAX_METADATA_BYTES = 128 * 1024
private const val DEFAULT_REFRESH_SECONDS = 30L
private const val REFRESH_GRACE_SECONDS = 2L
private const val MIN_REFRESH_SECONDS = 15L
private const val MAX_REFRESH_SECONDS = 5 * 60L
