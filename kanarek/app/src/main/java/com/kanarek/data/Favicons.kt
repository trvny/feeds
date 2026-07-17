package com.kanarek.data

import java.net.URI

/**
 * Favicon-based logo fallback for stations that have no `tvg-logo` and no iptv-org match
 * (see [StationLogos]) — which in practice means most hand-added or directory-added radio
 * stations. The station's stream host usually shares a domain with the broadcaster's site,
 * so its favicon via the Google s2 / DuckDuckGo icon services is a decent stand-in.
 *
 * Pure Kotlin (java.net only, no Android deps) so the host extraction is JVM-unit-tested.
 * Both services return an image for essentially any host (Google serves a generic globe on
 * a miss), so a favicon URL is "best effort by construction" — the UI still keeps the
 * drawable glyph as the final fallback for the offline case.
 */
object Favicons {
    /**
     * Ordered fallback candidates for a station's logo: the explicit [Station.logoUrl] first
     * (when set), then the Google s2 favicon for the stream host, then the DuckDuckGo one.
     * Empty only when the station has no logo *and* no parseable stream host.
     */
    fun logoChain(station: Station): List<String> {
        val out = mutableListOf<String>()
        station.logoUrl?.takeIf { it.isNotBlank() }?.let { out += it }
        hostOf(station.streamUrl)?.let { host ->
            out += "https://www.google.com/s2/favicons?domain=$host&sz=128"
            out += "https://icons.duckduckgo.com/ip3/$host.ico"
        }
        return out
    }

    /** First favicon candidate for [streamUrl]'s host, or null if the host can't be parsed. */
    fun firstFor(streamUrl: String): String? =
        hostOf(streamUrl)?.let { "https://www.google.com/s2/favicons?domain=$it&sz=128" }

    /**
     * The registrable-ish host of [url]: lowercased, port stripped, `www.` prefix dropped.
     * Returns null for anything that doesn't parse as an http(s) URL with a host — favicons
     * for raw IPs are still attempted (some radio streams live on bare IP:port, and DDG/Google
     * simply serve their generic icon for them, which the UI's drawable fallback then replaces
     * on error only if the services themselves fail).
     */
    fun hostOf(url: String): String? =
        runCatching {
            val uri = URI(url.trim())
            if (uri.scheme?.lowercase() !in setOf("http", "https")) return null
            uri.host?.lowercase()?.removePrefix("www.")?.takeIf { it.isNotBlank() }
        }.getOrNull()
}
