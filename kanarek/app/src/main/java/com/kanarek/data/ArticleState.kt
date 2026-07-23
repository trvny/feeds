package com.kanarek.data

import java.nio.charset.StandardCharsets.UTF_8
import java.util.Base64

enum class ArticleListFilter { ALL, UNREAD, SAVED }

data class ArticleState(
    val readIds: Set<String> = emptySet(),
    val savedArticles: List<NewsItem> = emptyList(),
    val hiddenIds: Set<String> = emptySet(),
) {
    val savedIds: Set<String> = savedArticles.mapTo(linkedSetOf()) { ArticleStates.id(it) }

    fun isRead(item: NewsItem): Boolean = ArticleStates.id(item) in readIds

    fun isSaved(item: NewsItem): Boolean = ArticleStates.id(item) in savedIds
}

object ArticleStates {
    fun id(item: NewsItem): String = item.link.trim()

    fun visible(
        feedItems: List<NewsItem>,
        state: ArticleState,
        filter: ArticleListFilter,
    ): List<NewsItem> {
        val candidates =
            when (filter) {
                ArticleListFilter.SAVED -> state.savedArticles.sortedByDescending { it.publishedAtMillis ?: 0L }
                ArticleListFilter.ALL,
                ArticleListFilter.UNREAD,
                -> feedItems
            }

        return candidates
            .distinctBy(::id)
            .filterNot { id(it) in state.hiddenIds }
            .filter { filter != ArticleListFilter.UNREAD || id(it) !in state.readIds }
    }
}

internal data class TimedArticleId(
    val id: String,
    val touchedAtMillis: Long,
)

internal object ArticleIdHistory {
    private const val VERSION = "1"
    private val encoder = Base64.getUrlEncoder().withoutPadding()
    private val decoder = Base64.getUrlDecoder()

    fun ids(records: Set<String>): Set<String> =
        records.mapNotNullTo(linkedSetOf()) { record ->
            decode(record)?.id ?: legacyId(record)
        }

    fun touch(
        records: Set<String>,
        id: String,
        nowMillis: Long,
        maxAgeMillis: Long,
        maxCount: Int,
    ): Set<String> =
        prune(
            records = records + encode(TimedArticleId(id.trim(), nowMillis)),
            nowMillis = nowMillis,
            maxAgeMillis = maxAgeMillis,
            maxCount = maxCount,
        )

    fun prune(
        records: Set<String>,
        nowMillis: Long,
        maxAgeMillis: Long,
        maxCount: Int,
    ): Set<String> {
        if (maxCount <= 0) return emptySet()
        val cutoff = (nowMillis - maxAgeMillis.coerceAtLeast(0L)).coerceAtLeast(0L)
        return records
            .mapNotNull { record ->
                decode(record) ?: legacyId(record)?.let { TimedArticleId(it, nowMillis) }
            }
            .groupBy(TimedArticleId::id)
            .values
            .map { matches -> matches.maxBy(TimedArticleId::touchedAtMillis) }
            .filter { it.touchedAtMillis >= cutoff }
            .sortedWith(
                compareByDescending<TimedArticleId>(TimedArticleId::touchedAtMillis)
                    .thenBy(TimedArticleId::id),
            )
            .take(maxCount)
            .mapTo(linkedSetOf(), ::encode)
    }

    private fun encode(record: TimedArticleId): String =
        listOf(
            VERSION,
            record.touchedAtMillis.toString(),
            encodeText(record.id),
        ).joinToString("|")

    private fun decode(record: String): TimedArticleId? =
        runCatching {
            val fields = record.split('|', limit = 3)
            if (fields.size != 3 || fields[0] != VERSION) return null
            val touchedAtMillis = fields[1].toLongOrNull() ?: return null
            val id = decodeText(fields[2]).trim()
            TimedArticleId(id, touchedAtMillis).takeIf { it.id.isNotBlank() }
        }.getOrNull()

    private fun legacyId(record: String): String? =
        record.trim().takeIf { it.isNotBlank() && !it.startsWith("$VERSION|") }

    private fun encodeText(value: String): String = encoder.encodeToString(value.toByteArray(UTF_8))

    private fun decodeText(value: String): String = String(decoder.decode(value), UTF_8)
}

internal object SavedArticleCodec {
    private const val VERSION = "1"
    private val encoder = Base64.getUrlEncoder().withoutPadding()
    private val decoder = Base64.getUrlDecoder()

    fun encode(item: NewsItem): String =
        listOf(
            VERSION,
            encodeText(item.title),
            encodeText(item.link),
            encodeText(item.summary),
            encodeText(item.imageUrl.orEmpty()),
            encodeText(item.source),
            item.publishedAtMillis?.toString().orEmpty(),
        ).joinToString("|")

    fun decode(record: String): NewsItem? =
        runCatching {
            val fields = record.split('|', limit = 7)
            if (fields.size != 7 || fields[0] != VERSION) return null
            NewsItem(
                title = decodeText(fields[1]),
                link = decodeText(fields[2]),
                summary = decodeText(fields[3]),
                imageUrl = decodeText(fields[4]).takeIf { it.isNotBlank() },
                source = decodeText(fields[5]),
                publishedAtMillis = fields[6].toLongOrNull(),
            ).takeIf { it.link.isNotBlank() }
        }.getOrNull()

    fun decodeAll(records: Set<String>): List<NewsItem> =
        records.mapNotNull(::decode).distinctBy(ArticleStates::id)

    private fun encodeText(value: String): String = encoder.encodeToString(value.toByteArray(UTF_8))

    private fun decodeText(value: String): String = String(decoder.decode(value), UTF_8)
}
