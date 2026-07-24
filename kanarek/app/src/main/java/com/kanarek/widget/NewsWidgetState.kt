package com.kanarek.widget

import com.kanarek.data.NewsItem
import java.nio.charset.StandardCharsets.UTF_8
import java.util.Base64

internal data class NewsWidgetConfig(
    val feeds: List<String>,
    val headlines: Boolean,
    val intervalSeconds: Int,
)

internal object NewsWidgetConfigs {
    fun migrate(
        stored: NewsWidgetConfig?,
        global: NewsWidgetConfig,
    ): NewsWidgetConfig = normalize(stored ?: global, global.feeds)

    fun normalize(
        config: NewsWidgetConfig,
        fallbackFeeds: List<String>,
    ): NewsWidgetConfig {
        val feeds =
            config.feeds
                .map(String::trim)
                .filter(String::isNotEmpty)
                .distinct()
                .ifEmpty {
                    fallbackFeeds
                        .map(String::trim)
                        .filter(String::isNotEmpty)
                        .distinct()
                }
        return config.copy(
            feeds = feeds,
            intervalSeconds = config.intervalSeconds.coerceIn(3, 120),
        )
    }
}

internal data class NewsWidgetSnapshot(
    val items: List<NewsItem>,
    val lastUpdatedMillis: Long,
)

internal object NewsWidgetSnapshotCodec {
    private const val VERSION = "1"
    private val encoder = Base64.getUrlEncoder().withoutPadding()
    private val decoder = Base64.getUrlDecoder()

    fun encode(snapshot: NewsWidgetSnapshot): String =
        buildList {
            add("$VERSION|${snapshot.lastUpdatedMillis}")
            snapshot.items.take(MAX_ITEMS).forEach { item ->
                add(
                    listOf(
                        encodeText(item.title.take(MAX_TITLE_CHARS)),
                        encodeText(item.link.take(MAX_URL_CHARS)),
                        encodeText(item.summary.take(MAX_SUMMARY_CHARS)),
                        encodeText(item.imageUrl.orEmpty().take(MAX_URL_CHARS)),
                        encodeText(item.source.take(MAX_SOURCE_CHARS)),
                        item.publishedAtMillis?.toString().orEmpty(),
                    ).joinToString("|"),
                )
            }
        }.joinToString("\n")

    fun decode(raw: String?): NewsWidgetSnapshot? =
        runCatching {
            val lines = raw.orEmpty().lineSequence().filter(String::isNotBlank).toList()
            val header = lines.firstOrNull()?.split('|', limit = 2) ?: return null
            if (header.size != 2 || header[0] != VERSION) return null
            val updated = header[1].toLongOrNull()?.takeIf { it > 0L } ?: return null
            val items =
                lines.drop(1).mapNotNull { line ->
                    val fields = line.split('|', limit = 6)
                    if (fields.size != 6) return@mapNotNull null
                    NewsItem(
                        title = decodeText(fields[0]),
                        link = decodeText(fields[1]),
                        summary = decodeText(fields[2]),
                        imageUrl = decodeText(fields[3]).takeIf(String::isNotBlank),
                        source = decodeText(fields[4]),
                        publishedAtMillis = fields[5].toLongOrNull(),
                    ).takeIf { it.link.isNotBlank() }
                }.distinctBy { it.link.trim() }
            NewsWidgetSnapshot(items = items, lastUpdatedMillis = updated)
        }.getOrNull()

    private fun encodeText(value: String): String = encoder.encodeToString(value.toByteArray(UTF_8))

    private fun decodeText(value: String): String = String(decoder.decode(value), UTF_8)

    private const val MAX_ITEMS = 12
    private const val MAX_TITLE_CHARS = 500
    private const val MAX_URL_CHARS = 2_048
    private const val MAX_SUMMARY_CHARS = 4_000
    private const val MAX_SOURCE_CHARS = 300
}
