package com.feedy.data

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Turns a plain website URL into something the feed list can hold, via the Worker.
 *
 *  - [discover] asks the Worker's `/discover` for a site's native RSS/Atom. Most
 *    sites that "have no RSS" actually advertise one in their page head; this
 *    finds it so we can subscribe to the real feed.
 *  - [scrapeUrl] builds a Worker `/scrape` URL for sites with no native feed. The
 *    Worker returns Atom, so the URL behaves like any other feed in both on-device
 *    and backend modes and round-trips through OPML unchanged.
 *
 * Pure Kotlin, no Android deps (mirrors [Opml]); call off the main thread.
 */
object SiteSubscribe {

    data class Discovered(val url: String, val title: String, val type: String)

    /** Native feeds the Worker found for [siteUrl]. Empty = none advertised. */
    fun discover(backend: String, siteUrl: String): List<Discovered> {
        val base = backend.trimEnd('/')
        val q = URLEncoder.encode(siteUrl, "UTF-8")
        val body = httpGet("$base/discover?url=$q")
        val arr = JSONObject(body).optJSONArray("feeds") ?: return emptyList()
        return (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            val u = o.optString("url").takeIf { it.isNotBlank() } ?: return@mapNotNull null
            Discovered(u, o.optString("title"), o.optString("type"))
        }
    }

    /** Worker `/scrape` URL for [siteUrl] — add it to the feed list as-is. */
    fun scrapeUrl(backend: String, siteUrl: String): String {
        val base = backend.trimEnd('/')
        val q = URLEncoder.encode(siteUrl, "UTF-8")
        return "$base/scrape?url=$q"
    }

    private fun httpGet(urlStr: String): String {
        val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
            connectTimeout = TIMEOUT_MS
            readTimeout = TIMEOUT_MS
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/json")
        }
        try {
            if (conn.responseCode !in 200..299) error("HTTP ${conn.responseCode} for $urlStr")
            return conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    private const val TIMEOUT_MS = 8_000
    private const val USER_AGENT = "feedy/1.0 (Android; +https://github.com/travino/feedy)"
}
