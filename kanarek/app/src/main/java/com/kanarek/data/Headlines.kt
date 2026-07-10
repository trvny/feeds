package com.kanarek.data

import kotlin.math.exp
import kotlin.math.ln

/**
 * Ranks news items by "hotness" for the headlines / showcase view, using only the
 * signals already present on a [NewsItem]. Pure Kotlin (no Android deps) so it can run
 * in both backend and on-device modes and be unit-tested like [FeedParser] / [Opml].
 *
 * Score is the sum of four signals:
 *  - **recency**     — exponential decay, 1.0 at age 0, halving every [HALF_LIFE_HOURS].
 *  - **image**       — a flat bonus; an item with a picture is more cover-worthy.
 *  - **top source**  — a flat bonus when the item's source is in the caller's top set.
 *  - **corroboration** — the strongest signal: the same story surfacing from several
 *    distinct sources. Items are clustered by title-token similarity and every item in a
 *    cluster scores (distinctSources - 1) * [CORROBORATION_BONUS].
 *
 * Corroboration trades precision for recall — unrelated items that share enough
 * distinctive words can cluster — so it is one signal among several, not the whole score.
 */
object Headlines {
    data class Scored(
        val item: NewsItem,
        val score: Double,
    )

    private const val HALF_LIFE_HOURS = 8.0
    private const val IMAGE_BONUS = 0.5
    private const val TOP_SOURCE_BONUS = 1.0
    private const val CORROBORATION_BONUS = 1.5
    private const val MIN_TOKENS_TO_CLUSTER = 2
    private const val JACCARD_THRESHOLD = 0.5
    private const val MIN_TOKEN_LEN = 4

    /** Sensible cover-worthy sources used when the caller supplies no top set. */
    val DEFAULT_TOP_SOURCES: Set<String> = setOf("google news", "euronews", "antyweb")

    /** Common PL+EN words that carry no topical signal, excluded from clustering. */
    private val STOPWORDS: Set<String> =
        setOf(
            "this",
            "that",
            "with",
            "from",
            "have",
            "will",
            "your",
            "about",
            "after",
            "could",
            "would",
            "their",
            "there",
            "these",
            "those",
            "what",
            "when",
            "into",
            "over",
            "more",
            "than",
            "they",
            "been",
            "were",
            "said",
            "także",
            "przez",
            "oraz",
            "jest",
            "będzie",
            "który",
            "która",
            "które",
            "jako",
            "jednak",
            "tylko",
            "bardzo",
            "może",
            "tego",
            "jego",
            "dla",
            "nie",
            "się",
            "już",
            "czy",
            "ale",
        )

    /** Top [limit] items by score (newest-first within score ties). */
    fun headlines(
        items: List<NewsItem>,
        topSources: Set<String> = DEFAULT_TOP_SOURCES,
        limit: Int = 6,
        nowMillis: Long = System.currentTimeMillis(),
    ): List<NewsItem> = rank(items, topSources, nowMillis).take(limit).map { it.item }

    /** All items scored and sorted hottest-first. */
    fun rank(
        items: List<NewsItem>,
        topSources: Set<String> = DEFAULT_TOP_SOURCES,
        nowMillis: Long = System.currentTimeMillis(),
    ): List<Scored> {
        if (items.isEmpty()) return emptyList()
        val tops = topSources.map { it.lowercase().trim() }.filter { it.isNotEmpty() }.toSet()
        val corroboration = corroborationByIndex(items)
        return items
            .mapIndexed { i, it -> Scored(it, score(it, tops, corroboration[i], nowMillis)) }
            .sortedWith(
                compareByDescending<Scored> { it.score }
                    .thenByDescending { it.item.publishedAtMillis ?: 0L },
            )
    }

    private fun score(
        item: NewsItem,
        tops: Set<String>,
        corroboration: Int,
        now: Long,
    ): Double {
        var s = 0.0
        item.publishedAtMillis?.let { ts ->
            val ageHours = (now - ts).coerceAtLeast(0L) / 3_600_000.0
            s += exp(-ln(2.0) / HALF_LIFE_HOURS * ageHours)
        }
        if (!item.imageUrl.isNullOrBlank()) s += IMAGE_BONUS
        if (item.source.lowercase().trim() in tops) s += TOP_SOURCE_BONUS
        s += corroboration * CORROBORATION_BONUS
        return s
    }

    /** For each item index, how many *other distinct sources* cover the same story. */
    private fun corroborationByIndex(items: List<NewsItem>): IntArray {
        val tokens = items.map { significantTokens(it.title) }
        val uf = UnionFind(items.size)
        for (i in items.indices) {
            if (tokens[i].size < MIN_TOKENS_TO_CLUSTER) continue
            for (j in i + 1 until items.size) {
                if (tokens[j].size < MIN_TOKENS_TO_CLUSTER) continue
                if (jaccard(tokens[i], tokens[j]) >= JACCARD_THRESHOLD) uf.union(i, j)
            }
        }
        // distinct sources per cluster root
        val clusterSources = HashMap<Int, MutableSet<String>>()
        for (i in items.indices) {
            clusterSources.getOrPut(uf.find(i)) { mutableSetOf() }.add(items[i].source.lowercase().trim())
        }
        return IntArray(items.size) { i ->
            ((clusterSources[uf.find(i)]?.size ?: 1) - 1).coerceAtLeast(0)
        }
    }

    private fun significantTokens(title: String): Set<String> =
        title
            .lowercase()
            .replace(Regex("[^\\p{L}\\p{Nd} ]"), " ")
            .split(Regex("\\s+"))
            .filter { it.length >= MIN_TOKEN_LEN && it !in STOPWORDS }
            .toSet()

    private fun jaccard(
        a: Set<String>,
        b: Set<String>,
    ): Double {
        if (a.isEmpty() || b.isEmpty()) return 0.0
        val inter = a.count { it in b }
        val union = a.size + b.size - inter
        return if (union == 0) 0.0 else inter.toDouble() / union
    }

    /** Minimal union-find for clustering item indices. */
    private class UnionFind(
        n: Int,
    ) {
        private val parent = IntArray(n) { it }

        fun find(x: Int): Int {
            var r = x
            while (parent[r] != r) r = parent[r]
            var c = x
            while (parent[c] != c) {
                val next = parent[c]
                parent[c] = r
                c = next
            }
            return r
        }

        fun union(
            a: Int,
            b: Int,
        ) {
            val ra = find(a)
            val rb = find(b)
            if (ra != rb) parent[ra] = rb
        }
    }
}
