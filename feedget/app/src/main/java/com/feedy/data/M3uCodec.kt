package com.feedy.data

import java.net.URI
import java.security.MessageDigest

/**
 * Minimal M3U/M3U8 playlist reader/writer for IPTV channels and internet radio stations — pure
 * Kotlin, no Android deps (mirrors [Opml]). Understands the common `#EXTINF` extension used by
 * IPTV lists (`tvg-logo`, `group-title`); tolerant of malformed/minimal input — it never throws,
 * it just returns whatever entries it could find. This is also the on-disk/DataStore station-list
 * encoding (see `SettingsStore.stations`), so persistence and import/export share one format.
 */
object M3uCodec {

    private val ATTR = Regex("""([\w-]+)\s*=\s*"([^"]*)"""")

    /** Parse M3U/M3U8 text into a station list, de-duped by stream URL (first occurrence wins). */
    fun parse(text: String): List<Station> {
        val stations = mutableListOf<Station>()
        var pendingName: String? = null
        var pendingLogo: String? = null
        var pendingGroup: String? = null

        text.lineSequence().map { it.trim() }.filter { it.isNotEmpty() }.forEach { line ->
            when {
                line.startsWith("#EXTINF", ignoreCase = true) -> {
                    val body = line.substringAfter(':', missingDelimiterValue = "").trim()
                    val lastQuote = body.lastIndexOf('"')
                    val attrsPart: String
                    val title: String
                    if (lastQuote >= 0) {
                        // Attributes are always quoted and come first, so everything after the
                        // last quote is the title — robust even if a quoted value (e.g.
                        // group-title="News, Sports") itself contains a comma.
                        attrsPart = body.substring(0, lastQuote + 1)
                        title = body.substring(lastQuote + 1).removePrefix(",").trim()
                    } else {
                        // No quoted attributes: plain "duration,Title" form.
                        val comma = body.indexOf(',')
                        attrsPart = if (comma >= 0) body.substring(0, comma) else body
                        title = if (comma >= 0) body.substring(comma + 1).trim() else ""
                    }
                    val attrs = ATTR.findAll(attrsPart)
                        .associate { it.groupValues[1].lowercase() to it.groupValues[2].trim() }
                    pendingName = title.ifEmpty { null }
                    pendingLogo = attrs["tvg-logo"]?.ifEmpty { null }
                    pendingGroup = attrs["group-title"]?.ifEmpty { null }
                }
                line.startsWith("#") -> {
                    // Other tags (#EXTM3U, #EXTVLCOPT, #EXTGRP, ...) — not needed, skip.
                }
                else -> {
                    val url = line
                    stations += Station(
                        id = hash(url),
                        name = pendingName?.takeIf { it.isNotBlank() } ?: labelOf(url),
                        streamUrl = url,
                        logoUrl = pendingLogo,
                        groupTitle = pendingGroup,
                    )
                    pendingName = null
                    pendingLogo = null
                    pendingGroup = null
                }
            }
        }
        return stations.distinctBy { it.streamUrl }
    }

    /** The same stable id [parse] would assign to this URL — use when constructing a new
     *  [Station] by hand (e.g. the "add station" dialog) so it matches what a later
     *  persist-then-reload round-trip via [parse] produces for the same URL. */
    fun idFor(url: String): String = hash(url.trim())

    /** Serialize a station list to an M3U8 playlist (`#EXTM3U` + one `#EXTINF`/URL pair each). */
    fun build(stations: List<Station>): String = buildString {
        append("#EXTM3U\n")
        stations.forEach { s ->
            val attrs = buildString {
                s.logoUrl?.takeIf { it.isNotBlank() }?.let { append(" tvg-logo=\"").append(clean(it)).append('"') }
                s.groupTitle?.takeIf { it.isNotBlank() }?.let { append(" group-title=\"").append(clean(it)).append('"') }
            }
            append("#EXTINF:-1").append(attrs).append(',').append(clean(s.name)).append('\n')
            append(s.streamUrl.trim()).append('\n')
        }
    }

    /** A friendly fallback label when a line has no `#EXTINF` title: the URL's host, or the URL. */
    private fun labelOf(url: String): String =
        runCatching { URI(url).host?.removePrefix("www.") }.getOrNull()?.takeIf { it.isNotBlank() } ?: url

    /** M3U has no formal escaping — strip characters that would corrupt the line structure. */
    private fun clean(s: String): String = s.replace("\"", "").replace("\n", " ").trim()

    private fun hash(s: String): String =
        MessageDigest.getInstance("SHA-1").digest(s.toByteArray())
            .joinToString("") { "%02x".format(it.toInt() and 0xFF) }
}
