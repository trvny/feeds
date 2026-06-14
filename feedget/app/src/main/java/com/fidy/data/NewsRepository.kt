package com.fidy.data

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
 */
class NewsRepository {

    /** Blocking fetch — safe to call from a background thread (e.g. the widget factory). */
    fun fetchBlocking(feeds: List<String>, backendUrl: String = "", limit: Int = 20): List<NewsItem> {
        if (backendUrl.isNotBlank()) {
            runCatching { return fetchFromBackend(backendUrl, feeds, limit) }
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

    suspend fun fetch(feeds: List<String>, backendUrl: String = "", limit: Int = 20): List<NewsItem> =
        withContext(Dispatchers.IO) { fetchBlocking(feeds, backendUrl, limit) }

    private fun fetchFromBackend(backendUrl: String, feeds: List<String>, limit: Int): List<NewsItem> {
        val base = backendUrl.trimEnd('/')
        val feedsParam = URLEncoder.encode(feeds.joinToString(","), "UTF-8")
        val json = download("$base/?feeds=$feedsParam&limit=$limit")
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
        private const val USER_AGENT = "fidy/1.0 (Android; +https://github.com/travino/fidy)"

        val DEFAULT_FEEDS = listOf(
            "https://hnrss.org/frontpage",
            "https://www.theverge.com/rss/index.xml",
        )
    }
}
