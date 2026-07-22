package com.kanarek.data

import java.net.URI
import java.security.MessageDigest

/**
 * Minimal M3U/M3U8 playlist reader/writer for IPTV channels and internet radio stations — pure
 * Kotlin, no Android deps (mirrors [Opml]). Understands the common `#EXTINF` extension used by
 * IPTV lists (`tvg-id`, `tvg-logo`, `group-title`, `user-agent`, `referrer`) plus VLC-style per-stream
 * `#EXTVLCOPT:http-user-agent=`/`#EXTVLCOPT:http-referrer=` lines as a fallback for lists that
 * only carry headers that way; tolerant of malformed/minimal input — it never throws, it just
 * returns whatever entries it could find. This is also the on-disk/DataStore station-list
 * encoding (see `SettingsStore.stations`), so persistence and import/export share one format.
 */
object M3uCodec {
    private val ATTR = Regex("""([\w-]+)\s*=\s*"([^"]*)"""")

    /** Parse M3U/M3U8 text into a station list, de-duped by stream URL (first occurrence wins). */
    fun parse(text: String): List<Station> {
        val stations = mutableListOf<Station>()
        var pendingName: String? = null
        var pendingTvgId: String? = null
        var pendingLogo: String? = null
        var pendingGroup: String? = null
        var pendingUserAgent: String? = null
        var pendingReferrer: String? = null
        var pendingKind: StationKind = StationKind.UNKNOWN

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
                    val attrs =
                        ATTR
                            .findAll(attrsPart)
                            .associate { it.groupValues[1].lowercase() to it.groupValues[2].trim() }
                    pendingName = title.ifEmpty { null }
                    pendingTvgId = attrs["tvg-id"]?.ifEmpty { null }
                    pendingLogo = attrs["tvg-logo"]?.ifEmpty { null }
                    pendingGroup = attrs["group-title"]?.ifEmpty { null }
                    pendingUserAgent = attrs["user-agent"]?.ifEmpty { null }
                    pendingReferrer = attrs["referrer"]?.ifEmpty { null }
                    pendingKind = kindOf(attrs["kanarek-kind"])
                }

                line.startsWith("#EXTVLCOPT", ignoreCase = true) -> {
                    // VLC-style per-stream header options — fallback/override for lists that
                    // don't also repeat user-agent/referrer as quoted #EXTINF attributes.
                    val body = line.substringAfter(':', missingDelimiterValue = "")
                    val eq = body.indexOf('=')
                    if (eq > 0) {
                        val value = body.substring(eq + 1).trim()
                        if (value.isNotEmpty()) {
                            when (body.substring(0, eq).trim().lowercase()) {
                                "http-user-agent" -> pendingUserAgent = value
                                "http-referrer", "http-referer" -> pendingReferrer = value
                            }
                        }
                    }
                }

                line.startsWith("#EXTGRP:", ignoreCase = true) ||
                    line.startsWith("#EXTALB:", ignoreCase = true) -> {
                    // Some radio playlists put the station family/category on its own line rather
                    // than in EXTINF's group-title attribute. Keep an explicit group-title when one
                    // exists; otherwise accept EXTGRP (standard-ish) and EXTALB (common in exports).
                    val value = line.substringAfter(':', missingDelimiterValue = "").trim()
                    if (pendingGroup.isNullOrBlank() && value.isNotEmpty()) pendingGroup = value
                }

                line.startsWith("#") -> {
                    // Other tags (#EXTM3U, artwork metadata, ...) — not needed, skip.
                }

                else -> {
                    val url = line
                    stations +=
                        Station(
                            id = hash(url),
                            name = pendingName?.takeIf { it.isNotBlank() } ?: labelOf(url),
                            streamUrl = url,
                            logoUrl = pendingLogo,
                            groupTitle = pendingGroup,
                            tvgId = pendingTvgId,
                            userAgent = pendingUserAgent,
                            referrer = pendingReferrer,
                            kind =
                                if (pendingKind != StationKind.UNKNOWN) {
                                    pendingKind
                                } else {
                                    inferKind(pendingName, pendingGroup, pendingTvgId, url)
                                },
                        )
                    pendingName = null
                    pendingTvgId = null
                    pendingLogo = null
                    pendingGroup = null
                    pendingUserAgent = null
                    pendingReferrer = null
                    pendingKind = StationKind.UNKNOWN
                }
            }
        }
        return stations.distinctBy { it.streamUrl }
    }

    /** The same stable id [parse] would assign to this URL — use when constructing a new
     *  [Station] by hand (e.g. the "add station" dialog) so it matches what a later
     *  persist-then-reload round-trip via [parse] produces for the same URL. */
    fun idFor(url: String): String = hash(url.trim())

    /** Serialize a station list to an M3U8 playlist (`#EXTM3U` + one `#EXTINF`/URL pair each,
     *  plus `#EXTVLCOPT` header lines for entries carrying [Station.userAgent]/[Station.referrer]
     *  so VLC-family players honor them too). */
    fun build(stations: List<Station>): String =
        buildString {
            append("#EXTM3U\n")
            stations.forEach { s ->
                val attrs =
                    buildString {
                        s.tvgId?.takeIf { it.isNotBlank() }?.let { append(" tvg-id=\"").append(clean(it)).append('"') }
                        s.logoUrl?.takeIf { it.isNotBlank() }?.let { append(" tvg-logo=\"").append(clean(it)).append('"') }
                        s.groupTitle?.takeIf { it.isNotBlank() }?.let { append(" group-title=\"").append(clean(it)).append('"') }
                        s.userAgent?.takeIf { it.isNotBlank() }?.let { append(" user-agent=\"").append(clean(it)).append('"') }
                        s.referrer?.takeIf { it.isNotBlank() }?.let { append(" referrer=\"").append(clean(it)).append('"') }
                        kindTag(s.kind)?.let { append(" kanarek-kind=\"").append(it).append('"') }
                    }
                append("#EXTINF:-1")
                    .append(attrs)
                    .append(',')
                    .append(clean(s.name))
                    .append('\n')
                s.userAgent?.takeIf { it.isNotBlank() }?.let { append("#EXTVLCOPT:http-user-agent=").append(clean(it)).append('\n') }
                s.referrer?.takeIf { it.isNotBlank() }?.let { append("#EXTVLCOPT:http-referrer=").append(clean(it)).append('\n') }
                append(s.streamUrl.trim()).append('\n')
            }
        }

    /**
     * Best-effort [StationKind] for an entry that carries no explicit `kanarek-kind` attribute —
     * external IPTV/radio playlists never do, which used to dump every imported station into the
     * "Other" tab with no video surface. Ordered checks: audio-only file extensions and
     * radio-ish words in the name/group mean radio (checked first, since plenty of internet
     * radios stream HLS `.m3u8` too); a `tvg-id` (the iptv-org join key) or a video
     * manifest/container URL means TV; anything else stays UNKNOWN. Pure and deterministic so
     * persisted lists saved before this heuristic existed get re-classified on their next read
     * through [parse] (persistence shares this codec).
     */
    fun inferKind(
        name: String?,
        groupTitle: String?,
        tvgId: String?,
        url: String,
    ): StationKind {
        val path = url.trim().lowercase().substringBefore('?').substringBefore('#')
        val audioExt = listOf(".mp3", ".aac", ".ogg", ".oga", ".opus", ".flac", ".m4a", ".pls", ".wav")
        if (audioExt.any { path.endsWith(it) }) return StationKind.RADIO
        val text = "${name.orEmpty()} ${groupTitle.orEmpty()}".lowercase()
        if (RADIO_WORD.containsMatchIn(text)) return StationKind.RADIO
        if (!tvgId.isNullOrBlank()) return StationKind.TV
        val videoExt = listOf(".m3u8", ".mpd", ".ts", ".mp4", ".mkv")
        if (videoExt.any { path.endsWith(it) } || "/hls/" in path || "/dash/" in path) return StationKind.TV
        return StationKind.UNKNOWN
    }

    private val RADIO_WORD = Regex("""(^|[^\p{L}])(radio|radia|radiowa|fm)([^\p{L}]|$)""")

    /** Map a `kanarek-kind` attribute value to a [StationKind]; anything unrecognized is UNKNOWN. */
    private fun kindOf(raw: String?): StationKind =
        when (raw?.trim()?.lowercase()) {
            "tv" -> StationKind.TV
            "radio" -> StationKind.RADIO
            else -> StationKind.UNKNOWN
        }

    /** The attribute value to serialize for a kind, or null for UNKNOWN (omit the attr entirely). */
    private fun kindTag(kind: StationKind): String? =
        when (kind) {
            StationKind.TV -> "tv"
            StationKind.RADIO -> "radio"
            StationKind.UNKNOWN -> null
        }

    /** A friendly fallback label when a line has no `#EXTINF` title: the URL's host, or the URL. */
    private fun labelOf(url: String): String =
        runCatching { URI(url).host?.removePrefix("www.") }.getOrNull()?.takeIf { it.isNotBlank() } ?: url

    /** M3U has no formal escaping — strip characters that would corrupt the line structure. */
    private fun clean(s: String): String = s.replace("\"", "").replace("\n", " ").trim()

    private fun hash(s: String): String =
        MessageDigest
            .getInstance("SHA-1")
            .digest(s.toByteArray())
            .joinToString("") { "%02x".format(it.toInt() and 0xFF) }
}
