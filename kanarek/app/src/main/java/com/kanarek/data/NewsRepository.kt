package com.kanarek.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.time.Instant

internal data class NewsFetchResult(
    val items: List<NewsItem>,
    val successfulSources: Int,
)

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
        perSourceCap: Int = 0,
    ): List<NewsItem> =
        fetchBlockingWithStatus(
            feeds = feeds,
            backendUrl = backendUrl,
            limit = limit,
            cache = cache,
            perSourceCap = perSourceCap,
        ).items

    internal fun fetchBlockingWithStatus(
        feeds: List<String>,
        backendUrl: String = "",
        limit: Int = 20,
        cache: FeedCache? = null,
        perSourceCap: Int = 0,
    ): NewsFetchResult {
        // When capping per source, over-fetch so there's enough material from each
        // feed to diversify from before trimming back down to [limit].
        val fetchLimit =
            if (perSourceCap > 0) {
                (limit * OVERFETCH_FACTOR).coerceAtMost(MAX_LIMIT)
            } else {
                limit
            }
        val selectedFeeds = feeds.take(MAX_FEEDS_PER_REQUEST)
        if (backendUrl.isNotBlank()) {
            val backendResult =
                runCatching {
                    fetchFromBackend(
                        backendUrl = backendUrl,
                        feeds = selectedFeeds,
                        limit = fetchLimit,
                        cache = cache,
                    )
                }
            if (backendResult.isSuccess) {
                return NewsFetchResult(
                    items = finalize(backendResult.getOrThrow(), limit, perSourceCap),
                    successfulSources = selectedFeeds.size,
                )
            }
            // Fall through to on-device parsing if the backend call fails.
        }
        // Fan the feeds out concurrently: a single slow/stalled host would otherwise serialise
        // the whole run (sum of every feed's timeout), leaving the reader spinning for minutes.
        // Each feed stays isolated so partial results still render.
        val results =
            runBlocking {
                selectedFeeds
                    .map { url ->
                        async(Dispatchers.IO) {
                            runCatching { FeedParser.parse(download(url)) }
                        }
                    }.awaitAll()
            }
        val all = results.flatMap { it.getOrDefault(emptyList()) }
        return NewsFetchResult(
            items = finalize(all.distinctBy { it.link }, limit, perSourceCap),
            successfulSources = results.count { it.isSuccess },
        )
    }

    /** Drop non-web links supplied by untrusted feeds, then cap/sort/trim the safe set. */
    private fun finalize(
        items: List<NewsItem>,
        limit: Int,
        perSourceCap: Int,
    ): List<NewsItem> {
        val safe = items.filter { WebLinks.isHttpOrHttps(it.link) }
        return if (perSourceCap > 0) {
            NewsMerge.capPerSource(safe, perSourceCap).take(limit)
        } else {
            safe.sortedByDescending { it.publishedAtMillis ?: 0L }.take(limit)
        }
    }

    suspend fun fetch(
        feeds: List<String>,
        backendUrl: String = "",
        limit: Int = 20,
        cache: FeedCache? = null,
        perSourceCap: Int = 0,
    ): List<NewsItem> =
        withContext(Dispatchers.IO) {
            fetchBlocking(feeds, backendUrl, limit, cache, perSourceCap)
        }

    internal suspend fun fetchWithStatus(
        feeds: List<String>,
        backendUrl: String = "",
        limit: Int = 20,
        cache: FeedCache? = null,
        perSourceCap: Int = 0,
    ): NewsFetchResult =
        withContext(Dispatchers.IO) {
            fetchBlockingWithStatus(feeds, backendUrl, limit, cache, perSourceCap)
        }

    private fun fetchFromBackend(
        backendUrl: String,
        feeds: List<String>,
        limit: Int,
        cache: FeedCache?,
    ): List<NewsItem> {
        val base = backendUrl.trimEnd('/')
        val feedsParam =
            URLEncoder.encode(
                feeds.take(MAX_FEEDS_PER_REQUEST).joinToString(","),
                "UTF-8",
            )
        val urlStr = "$base/?feeds=$feedsParam&limit=$limit"

        val key = cache?.keyFor(urlStr)
        val cached = if (cache != null && key != null) cache.read(key) else null

        val conn =
            (URL(urlStr).openConnection() as HttpURLConnection).apply {
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
                val body = cached?.body ?: error("304 without cached body for $urlStr")
                return parseBackendJson(body)
            }
            if (code !in 200..299) error("HTTP $code for $urlStr")
            val body = conn.inputStream.use { it.readTextCapped(MAX_BACKEND_BYTES) }
            val etag = conn.getHeaderField("ETag")
            if (cache != null && key != null && !etag.isNullOrBlank()) {
                cache.write(key, etag, body)
            }
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
        s
            ?.takeIf { it.isNotBlank() }
            ?.let { runCatching { Instant.parse(it).toEpochMilli() }.getOrNull() }

    private fun download(rawUrl: String): String {
        val conn =
            (URL(rawUrl).openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty(
                    "Accept",
                    "application/rss+xml, application/atom+xml, application/xml, " +
                        "text/xml, application/json",
                )
            }
        try {
            if (conn.responseCode !in 200..299) {
                error("HTTP ${conn.responseCode} for $rawUrl")
            }
            return conn.inputStream.use { it.readTextCapped(MAX_FEED_BYTES) }
        } finally {
            conn.disconnect()
        }
    }

    companion object {
        private const val TIMEOUT_MS = 8_000
        internal const val MAX_FEEDS_PER_REQUEST = 12
        private const val OVERFETCH_FACTOR = 5
        private const val MAX_LIMIT = 100
        private const val MAX_BACKEND_BYTES = 2 * 1024 * 1024
        private const val MAX_FEED_BYTES = 4 * 1024 * 1024
        private const val USER_AGENT = "kanarek/1.0 (Android; +https://github.com/trvny/feeds)"

        val DEFAULT_FEEDS =
            listOf(
                "https://news.google.com/atom?hl=pl&gl=PL&ceid=PL:pl",
                "https://pl.euronews.com/rss?format=mrss",
                "https://antyweb.pl/feed/",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_pap.xml",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_reuters.xml",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_wikipedia_pl.xml",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_daily_digest.xml",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_daily_quote.xml",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_jbzd.xml",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_beatport_top100.xml",
                "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_cloudflare.xml",
            )

        /** Deployed Cloudflare Worker — kanarek/worker/. */
        const val DEFAULT_BACKEND = "https://kanarek.travny.workers.dev"
    }
}
