package com.kanarek.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/** Plain-text article body returned by the Worker's safe reader endpoint. */
data class CleanArticle(
    val title: String,
    val author: String?,
    val imageUrl: String?,
    val content: String,
    val wordCount: Int,
)

/** Only an explicitly configured public HTTP(S) backend may receive opened article URLs. */
internal fun configuredReaderBackend(raw: String): String? =
    raw.trim()
        .takeIf { WebLinks.isHttpOrHttps(it) }
        ?.trimEnd('/')

/** Fetches an inert, advertisement-filtered article body. Feed summary remains the UI fallback. */
class ArticleReader {
    suspend fun fetch(
        articleUrl: String,
        backendUrl: String,
    ): CleanArticle? =
        withContext(Dispatchers.IO) {
            val backend = configuredReaderBackend(backendUrl) ?: return@withContext null
            if (!WebLinks.isHttpOrHttps(articleUrl)) return@withContext null
            val endpoint =
                "$backend/article?url=" +
                    URLEncoder.encode(articleUrl.trim(), Charsets.UTF_8.name())
            val connection =
                (URL(endpoint).openConnection() as HttpURLConnection).apply {
                    connectTimeout = TIMEOUT_MS
                    readTimeout = TIMEOUT_MS
                    instanceFollowRedirects = true
                    setRequestProperty("User-Agent", USER_AGENT)
                    setRequestProperty("Accept", "application/json")
                }
            try {
                if (connection.responseCode !in 200..299) return@withContext null
                val body = connection.inputStream.use { it.readTextCapped(MAX_RESPONSE_BYTES) }
                parse(body)
            } finally {
                connection.disconnect()
            }
        }

    internal fun parse(json: String): CleanArticle? {
        val objectValue = runCatching { JSONObject(json) }.getOrNull() ?: return null
        val content = objectValue.optString("content").trim()
        if (content.length < MIN_CONTENT_CHARS) return null
        return CleanArticle(
            title = objectValue.optString("title").trim().take(MAX_TITLE_CHARS),
            author =
                objectValue.optString("author").trim()
                    .takeIf { it.isNotEmpty() && !it.equals("null", ignoreCase = true) }
                    ?.take(MAX_AUTHOR_CHARS),
            imageUrl =
                objectValue.optString("image").trim()
                    .takeIf { WebLinks.isHttpOrHttps(it) },
            content = content.take(MAX_CONTENT_CHARS),
            wordCount =
                objectValue.optInt(
                    "wordCount",
                    content.split(Regex("\\s+")).count { it.isNotBlank() },
                ).coerceAtLeast(0),
        )
    }

    private companion object {
        const val TIMEOUT_MS = 9_000
        const val MAX_RESPONSE_BYTES = 512 * 1024
        const val MIN_CONTENT_CHARS = 220
        const val MAX_CONTENT_CHARS = 60_000
        const val MAX_TITLE_CHARS = 240
        const val MAX_AUTHOR_CHARS = 160
        const val USER_AGENT = "kanarek/1.0 (Android; +https://github.com/trvny/feeds)"
    }
}
