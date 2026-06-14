package com.fidy.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * Fetches and normalizes news from one or more RSS/Atom feeds.
 * Each feed is isolated: one failing URL can't sink the rest.
 */
class NewsRepository {

    /** Blocking fetch — safe to call from a background thread (e.g. the widget factory). */
    fun fetchBlocking(feeds: List<String>, limit: Int = 20): List<NewsItem> {
        val all = mutableListOf<NewsItem>()
        for (url in feeds.take(MAX_FEEDS)) {
            runCatching { all += FeedParser.parse(download(url)) }
        }
        return all
            .distinctBy { it.link }
            .sortedByDescending { it.publishedAtMillis ?: 0L }
            .take(limit)
    }

    suspend fun fetch(feeds: List<String>, limit: Int = 20): List<NewsItem> =
        withContext(Dispatchers.IO) { fetchBlocking(feeds, limit) }

    private fun download(feedUrl: String): String {
        val conn = (URL(feedUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = TIMEOUT_MS
            readTimeout = TIMEOUT_MS
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/rss+xml, application/atom+xml, application/xml, text/xml")
        }
        try {
            if (conn.responseCode !in 200..299) error("HTTP ${conn.responseCode} for $feedUrl")
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
