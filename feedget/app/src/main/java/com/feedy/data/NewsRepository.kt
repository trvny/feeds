package com.feedy.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.time.Instant

/**
 * Fetches and normalizes news from one or more RSS/Atom feeds.
 *
 * Two modes:
 *  - on-device (default): fetch + parse each feed here; one failing URL can't sink the rest.
 *  - backend: if a Cloudflare Worker URL is given, fetch normalized JSON from it instead
 *    (see worker/). Lets the device skip XML parsing and share an edge cache.
 *
 * Conditional GET (backend mode): when a [FeedCache] is supplied, the last response's ETag
 * is sent as `If-None-Match`. A `304 Not Modified` reuses the cached body instead of
 * re-downloading it — the device-side half of the Worker's ETag support.
 */
class NewsRepository {

    /** Blocking fetch — safe to call from a background thread (e.g. the widget factory). */
    fun fetchBlocking(
        feeds: List<String>,
        backendUrl: String = "",
        limit: Int = 20,
        cache: FeedCache? = null,
    ): List<NewsItem> {
        if (backendUrl.isNotBlank()) {
            runCatching { return fetchFromBackend(backendUrl, feeds, limit, cache) }
            // fall through to on-device parsing if the backend call fails
        }
        val all = mutableListOf<NewsItem>()
        for (url in feeds.take(MAX_FEEDS)) {
            runCatching { all += FeedParser.parse(download(url)) }
        }
        return all
            .distinctBy { it.link }
            .sortedByDescending { it.publishedAtMillis ?: 0L }
            .take(limit)
    }

    suspend fun fetch(
        feeds: List<String>,
        backendUrl: String = "",
        limit: Int = 20,
        cache: FeedCache? = null,
    ): List<NewsItem> =
        withContext(Dispatchers.IO) { fetchBlocking(feeds, backendUrl, limit, cache) }

    private fun fetchFromBackend(
        backendUrl: String,
        feeds: List<String>,
        limit: Int,
        cache: FeedCache?,
    ): List<NewsItem> {
        val base = backendUrl.trimEnd('/')
        val feedsParam = URLEncoder.encode(feeds.joinToString(","), "UTF-8")
        val urlStr = "$base/?feeds=$feedsParam&limit=$limit"

        val key = cache?.keyFor(urlStr)
        val cached = if (cache != null && key != null) cache.read(key) else null

        val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
            connectTimeout = TIMEOUT_MS
            readTimeout = TIMEOUT_MS
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/json")
            cached?.etag?.let { setRequestProperty("If-None-Match", it) }
        }
        try {
            val code = conn.responseCode
            if (code == HttpURLConnection.HTTP_NOT_MODIFIED) {
                // Nothing changed — reuse the cached body. If the cache was evicted out from
                // under us, throw so fetchBlocking falls through to on-device parsing.
                val body = cached?.body ?: error("304 without cached body for $urlStr")
                return parseBackendJson(body)
            }
            if (code !in 200..299) error("HTTP $code for $urlStr")
            val body = conn.inputStream.bufferedReader().use(BufferedReader::readText)
            val etag = conn.getHeaderField("ETag")
            if (cache != null && key != null && !etag.isNullOrBlank()) cache.write(key, etag, body)
            return parseBackendJson(body)
        } finally {
            conn.disconnect()
        }
    }

    private fun parseBackendJson(json: String): List<NewsItem> {
        val items = JSONObject(json).optJSONArray("items") ?: return emptyList()
        return (0 until items.length()).mapNotNull { i ->
            val o = items.optJSONObject(i) ?: return@mapNotNull null
            val title = o.optString("title").takeIf { it.isNotBlank() } ?: return@mapNotNull null
            val link = o.optString("link").takeIf { it.isNotBlank() } ?: return@mapNotNull null
            NewsItem(
                title = title,
                link = link,
                summary = o.optString("summary"),
                imageUrl = o.optString("image").takeIf { it.isNotBlank() },
                source = o.optString("source"),
                publishedAtMillis = parseIso(o.optString("date")),
            )
        }
    }

    private fun parseIso(s: String?): Long? =
        s?.takeIf { it.isNotBlank() }?.let { runCatching { Instant.parse(it).toEpochMilli() }.getOrNull() }

    private fun download(rawUrl: String): String {
        val conn = (URL(rawUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = TIMEOUT_MS
            readTimeout = TIMEOUT_MS
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/rss+xml, application/atom+xml, application/xml, text/xml, application/json")
        }
        try {
            if (conn.responseCode !in 200..299) error("HTTP ${conn.responseCode} for $rawUrl")
            return conn.inputStream.bufferedReader().use(BufferedReader::readText)
        } finally {
            conn.disconnect()
        }
    }

    companion object {
        private const val TIMEOUT_MS = 8_000
        private const val MAX_FEEDS = 12
        private const val USER_AGENT = "feedy/1.0 (Android; +https://github.com/travino/feedy)"

        val DEFAULT_FEEDS = listOf(
            "https://news.google.com/atom?hl=pl&gl=PL&ceid=PL:pl",
            "https://pl.euronews.com/rss?format=mrss",
            "https://antyweb.pl/feed/",
        )

        /**
         * Default hosted Worker for the "add a site without RSS" feature
         * (/discover + /scrape), used when the user hasn't set their own Backend
         * URL. Point this at your deployed Worker — `npx wrangler deploy` prints
         * the URL (https://feedy-news.<account>.workers.dev). Leave the app's
         * Backend URL blank to keep parsing normal feeds on-device while still
         * using this host only for discover/scrape.
         */
        const val DEFAULT_BACKEND = "https://feedy-news.travny.workers.dev"
    }
}
