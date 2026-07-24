package com.kanarek.data

import java.nio.charset.StandardCharsets.UTF_8
import java.util.Base64

enum class ArticleListFilter { ALL, UNREAD, SAVED }

data class ArticleState(
    val readIds: Set<String> = emptySet(),
    val savedArticles: List<NewsItem> = emptyList(),
    val hiddenIds: Set<String> = emptySet(),
    val offlineArticles: Map<String, OfflineArticleContent> = emptyMap(),
) {
    val savedIds: Set<String> = savedArticles.mapTo(linkedSetOf()) { ArticleStates.id(it) }
    val offlineArticleBytes: Long =
        offlineArticles.values.sumOf { SavedArticleCodec.offlineStorageBytes(it) }

    fun isRead(item: NewsItem): Boolean = ArticleStates.id(item) in readIds

    fun isSaved(item: NewsItem): Boolean = ArticleStates.id(item) in savedIds

    fun offlineArticle(item: NewsItem): OfflineArticleContent? = offlineArticles[ArticleStates.id(item)]
}

/** Plain reader text persisted with a saved-article snapshot. It is rendered as text, never HTML. */
data class OfflineArticleContent(
    val title: String,
    val author: String?,
    val imageUrl: String?,
    val content: String,
    val wordCount: Int,
    val storedAtMillis: Long,
) {
    fun asCleanArticle(): CleanArticle =
        CleanArticle(
            title = title,
            author = author,
            imageUrl = imageUrl,
            content = content,
            wordCount = wordCount,
        )
}

object ArticleStates {
    fun id(item: NewsItem): String = item.link.trim()

    fun visible(
        feedItems: List<NewsItem>,
        state: ArticleState,
        filter: ArticleListFilter,
        query: String = "",
        sources: Set<String> = emptySet(),
    ): List<NewsItem> {
        val candidates =
            when (filter) {
                ArticleListFilter.SAVED -> state.savedArticles.sortedByDescending { it.publishedAtMillis ?: 0L }
                ArticleListFilter.ALL,
                ArticleListFilter.UNREAD,
                -> feedItems
            }
        val normalizedQuery = query.trim()
        val normalizedSources =
            sources
                .map(::sourceKey)
                .filterTo(linkedSetOf(), String::isNotEmpty)

        return candidates
            .distinctBy(::id)
            .filterNot { id(it) in state.hiddenIds }
            .filter { filter != ArticleListFilter.UNREAD || id(it) !in state.readIds }
            .filter { normalizedSources.isEmpty() || sourceKey(it.source) in normalizedSources }
            .filter { item ->
                normalizedQuery.isEmpty() ||
                    sequenceOf(item.title, item.source, item.summary)
                        .any { it.contains(normalizedQuery, ignoreCase = true) }
            }
    }

    private fun sourceKey(source: String): String = source.trim().lowercase()
}

internal data class SavedArticleRecord(
    val item: NewsItem,
    val savedAtMillis: Long,
    val offline: OfflineArticleContent? = null,
)

internal object OfflineArticles {
    private val horizontalWhitespace = Regex("""[\t\x0B\f ]+""")

    fun fromCleanArticle(
        article: CleanArticle,
        storedAtMillis: Long,
    ): OfflineArticleContent? {
        val content = normalizeCleanText(article.content).take(MAX_CONTENT_CHARS)
        if (content.isBlank()) return null
        return OfflineArticleContent(
            title = normalizeCleanText(article.title).take(MAX_TITLE_CHARS),
            author =
                article.author
                    ?.let(::normalizeCleanText)
                    ?.take(MAX_AUTHOR_CHARS)
                    ?.takeIf(String::isNotBlank),
            imageUrl = article.imageUrl?.takeIf(WebLinks::isHttpOrHttps),
            content = content,
            wordCount = content.split(Regex("""\s+""")).count(String::isNotBlank),
            storedAtMillis = storedAtMillis,
        )
    }

    fun enforceLimit(
        records: List<SavedArticleRecord>,
        maxBytes: Long,
    ): List<SavedArticleRecord> {
        var totalBytes =
            records.sumOf { record ->
                record.offline?.let(SavedArticleCodec::offlineStorageBytes) ?: 0L
            }
        if (totalBytes <= maxBytes.coerceAtLeast(0L)) return records

        val removeOfflineFrom = linkedSetOf<String>()
        records
            .filter { it.offline != null }
            .sortedWith(
                compareBy<SavedArticleRecord>(SavedArticleRecord::savedAtMillis)
                    .thenBy { ArticleStates.id(it.item) },
            ).forEach { record ->
                if (totalBytes <= maxBytes.coerceAtLeast(0L)) return@forEach
                totalBytes -= record.offline?.let(SavedArticleCodec::offlineStorageBytes) ?: 0L
                removeOfflineFrom += ArticleStates.id(record.item)
            }
        return records.map { record ->
            if (ArticleStates.id(record.item) in removeOfflineFrom) {
                record.copy(offline = null)
            } else {
                record
            }
        }
    }

    /** CleanArticle fields are already inert plain text; do not parse angle brackets as markup. */
    private fun normalizeCleanText(raw: String): String =
        raw
            .replace('\u0000', ' ')
            .lineSequence()
            .map { horizontalWhitespace.replace(it, " ").trim() }
            .filter(String::isNotBlank)
            .joinToString("\n\n")
            .trim()

    private const val MAX_CONTENT_CHARS = 60_000
    private const val MAX_TITLE_CHARS = 240
    private const val MAX_AUTHOR_CHARS = 160
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
    private const val VERSION = "2"
    private const val LEGACY_VERSION = "1"
    private val encoder = Base64.getUrlEncoder().withoutPadding()
    private val decoder = Base64.getUrlDecoder()

    fun encode(item: NewsItem): String =
        encodeRecord(
            SavedArticleRecord(
                item = item,
                savedAtMillis = item.publishedAtMillis ?: 0L,
            ),
        )

    fun encodeRecord(record: SavedArticleRecord): String =
        listOf(
            VERSION,
            record.savedAtMillis.toString(),
            encodeText(record.item.title),
            encodeText(record.item.link),
            encodeText(record.item.summary),
            encodeText(record.item.imageUrl.orEmpty()),
            encodeText(record.item.source),
            record.item.publishedAtMillis?.toString().orEmpty(),
            record.offline?.storedAtMillis?.toString().orEmpty(),
            encodeText(record.offline?.title.orEmpty()),
            encodeText(record.offline?.author.orEmpty()),
            encodeText(record.offline?.imageUrl.orEmpty()),
            encodeText(record.offline?.content.orEmpty()),
            record.offline?.wordCount?.toString().orEmpty(),
        ).joinToString("|")

    fun decode(record: String): NewsItem? = decodeRecord(record)?.item

    fun decodeRecord(record: String): SavedArticleRecord? =
        runCatching {
            when {
                record.startsWith("$VERSION|") -> decodeCurrent(record)
                record.startsWith("$LEGACY_VERSION|") -> decodeLegacy(record)
                else -> null
            }
        }.getOrNull()

    fun decodeAll(records: Set<String>): List<NewsItem> =
        decodeRecords(records).map(SavedArticleRecord::item)

    fun decodeRecords(records: Set<String>): List<SavedArticleRecord> =
        records
            .mapNotNull(::decodeRecord)
            .groupBy { ArticleStates.id(it.item) }
            .values
            .map { matches ->
                matches.maxWith(
                    compareBy<SavedArticleRecord> { it.offline != null }
                        .thenBy(SavedArticleRecord::savedAtMillis),
                )
            }

    /** Persisted byte cost added by the Base64-encoded offline fields in a v2 record. */
    fun offlineStorageBytes(offline: OfflineArticleContent): Long =
        (
            offline.storedAtMillis.toString().length +
                encodeText(offline.title).length +
                encodeText(offline.author.orEmpty()).length +
                encodeText(offline.imageUrl.orEmpty()).length +
                encodeText(offline.content).length +
                offline.wordCount.toString().length
        ).toLong()

    private fun decodeCurrent(record: String): SavedArticleRecord? {
        val fields = record.split('|', limit = 14)
        if (fields.size != 14 || fields[0] != VERSION) return null
        val item =
            NewsItem(
                title = decodeText(fields[2]),
                link = decodeText(fields[3]),
                summary = decodeText(fields[4]),
                imageUrl = decodeText(fields[5]).takeIf(String::isNotBlank),
                source = decodeText(fields[6]),
                publishedAtMillis = fields[7].toLongOrNull(),
            ).takeIf { it.link.isNotBlank() } ?: return null
        val offlineContent = decodeText(fields[12])
        val offlineStoredAt = fields[8].toLongOrNull()
        val offline =
            if (offlineContent.isNotBlank() && offlineStoredAt != null) {
                OfflineArticleContent(
                    title = decodeText(fields[9]),
                    author = decodeText(fields[10]).takeIf(String::isNotBlank),
                    imageUrl =
                        decodeText(fields[11])
                            .takeIf(String::isNotBlank)
                            ?.takeIf(WebLinks::isHttpOrHttps),
                    content = offlineContent,
                    wordCount = fields[13].toIntOrNull()?.coerceAtLeast(0) ?: 0,
                    storedAtMillis = offlineStoredAt,
                )
            } else {
                null
            }
        return SavedArticleRecord(
            item = item,
            savedAtMillis = fields[1].toLongOrNull() ?: 0L,
            offline = offline,
        )
    }

    private fun decodeLegacy(record: String): SavedArticleRecord? {
        val fields = record.split('|', limit = 7)
        if (fields.size != 7 || fields[0] != LEGACY_VERSION) return null
        val item =
            NewsItem(
                title = decodeText(fields[1]),
                link = decodeText(fields[2]),
                summary = decodeText(fields[3]),
                imageUrl = decodeText(fields[4]).takeIf(String::isNotBlank),
                source = decodeText(fields[5]),
                publishedAtMillis = fields[6].toLongOrNull(),
            ).takeIf { it.link.isNotBlank() } ?: return null
        return SavedArticleRecord(
            item = item,
            savedAtMillis = item.publishedAtMillis ?: 0L,
        )
    }

    private fun encodeText(value: String): String = encoder.encodeToString(value.toByteArray(UTF_8))

    private fun decodeText(value: String): String = String(decoder.decode(value), UTF_8)
}
