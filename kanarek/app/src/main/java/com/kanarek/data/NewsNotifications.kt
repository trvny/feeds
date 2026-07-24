package com.kanarek.data

import java.nio.charset.StandardCharsets.UTF_8
import java.security.MessageDigest

data class NewsNotificationConfig(
    val enabled: Boolean = false,
    val selectedFeeds: List<String> = emptyList(),
    /** Feed catalogue seen when [selectedFeeds] was last reconciled. This lets a later feed edit
     * distinguish “follow every configured feed” from an intentional subset. */
    val configuredFeeds: List<String> = emptyList(),
    val quietHoursEnabled: Boolean = true,
    val quietStartMinute: Int = DEFAULT_QUIET_START_MINUTE,
    val quietEndMinute: Int = DEFAULT_QUIET_END_MINUTE,
) {
    fun normalized(): NewsNotificationConfig =
        copy(
            selectedFeeds = normalizeFeeds(selectedFeeds),
            configuredFeeds = normalizeFeeds(configuredFeeds),
            quietStartMinute = quietStartMinute.coerceIn(0, MINUTES_PER_DAY - 1),
            quietEndMinute = quietEndMinute.coerceIn(0, MINUTES_PER_DAY - 1),
        )

    /**
     * Drops deleted feed URLs and carries newly configured feeds forward only when the previous
     * selection represented “all”. An intentional subset stays a subset. If every selected feed
     * was deleted, fall back to the current catalogue instead of silently leaving an enabled
     * worker with nothing to monitor.
     */
    internal fun reconciledWith(feeds: List<String>): NewsNotificationConfig {
        val current = normalized()
        val available = normalizeFeeds(feeds)
        val availableSet = available.toSet()
        val surviving = current.selectedFeeds.filter { it in availableSet }
        val previouslyFollowedAll =
            current.configuredFeeds.isNotEmpty() &&
                current.configuredFeeds.all { it in current.selectedFeeds }
        val nextSelected =
            when {
                available.isEmpty() -> emptyList()
                previouslyFollowedAll -> available
                surviving.isNotEmpty() -> surviving
                else -> available
            }
        return current.copy(
            selectedFeeds = nextSelected,
            configuredFeeds = available,
        )
    }

    companion object {
        const val DEFAULT_QUIET_START_MINUTE = 22 * 60
        const val DEFAULT_QUIET_END_MINUTE = 7 * 60
        internal const val MINUTES_PER_DAY = 24 * 60

        private fun normalizeFeeds(feeds: List<String>): List<String> =
            feeds
                .map(String::trim)
                .filter(String::isNotEmpty)
                .distinct()
    }
}

internal data class NewsNotificationDecision(
    val knownIds: Set<String>,
    val newItems: List<NewsItem>,
    val shouldNotify: Boolean,
)

internal data class NewsNotificationSnapshot(
    val currentItems: List<NewsItem>,
    val knownIds: Set<String>,
    val initialized: Boolean,
    val minuteOfDay: Int,
    val config: NewsNotificationConfig,
)

internal object NewsNotificationPolling {
    fun feedBatches(
        feeds: List<String>,
        maxFeedsPerBatch: Int,
    ): List<List<String>> =
        if (maxFeedsPerBatch > 0) {
            feeds.chunked(maxFeedsPerBatch)
        } else {
            emptyList()
        }

    fun combine(
        results: List<NewsFetchResult>,
        limit: Int,
    ): NewsFetchResult {
        val items =
            results
                .asSequence()
                .flatMap { it.items.asSequence() }
                .filter { NewsNotifications.stableId(it).isNotBlank() }
                .distinctBy(NewsNotifications::stableId)
                .sortedByDescending { it.publishedAtMillis ?: 0L }
                .take(limit.coerceAtLeast(0))
                .toList()
        return NewsFetchResult(
            items = items,
            successfulSources = results.sumOf { it.successfulSources },
        )
    }

    fun shouldRecord(result: NewsFetchResult): Boolean = result.successfulSources > 0
}

internal object NewsNotifications {
    fun evaluate(
        snapshot: NewsNotificationSnapshot,
        maxKnownIds: Int = MAX_KNOWN_IDS,
    ): NewsNotificationDecision {
        val current =
            snapshot.currentItems
                .filter { stableId(it).isNotBlank() }
                .distinctBy(::stableId)
        val newItems =
            if (snapshot.initialized) {
                current.filterNot { stableId(it) in snapshot.knownIds }
            } else {
                emptyList()
            }
        val nextKnown = linkedSetOf<String>()
        val limit = maxKnownIds.coerceAtLeast(0)
        sequenceOf(
            current.asSequence().map(::stableId),
            snapshot.knownIds.asSequence().map(String::trim).filter(String::isNotEmpty),
        ).flatten()
            .forEach { id ->
                if (nextKnown.size < limit) nextKnown += id
            }
        val quiet =
            snapshot.config.quietHoursEnabled &&
                isQuietTime(
                    minuteOfDay = snapshot.minuteOfDay,
                    startMinute = snapshot.config.quietStartMinute,
                    endMinute = snapshot.config.quietEndMinute,
                )
        return NewsNotificationDecision(
            knownIds = nextKnown,
            newItems = newItems,
            shouldNotify = newItems.isNotEmpty() && !quiet,
        )
    }

    internal fun stableId(item: NewsItem): String {
        val link = ArticleStates.id(item)
        if (link.isBlank()) return ""
        val digest = MessageDigest.getInstance("SHA-256").digest(link.toByteArray(UTF_8))
        val alphabet = "0123456789abcdef"
        return buildString(digest.size * 2) {
            digest.forEach { byte ->
                val value = byte.toInt() and 0xff
                append(alphabet[value ushr 4])
                append(alphabet[value and 0x0f])
            }
        }
    }

    fun isQuietTime(
        minuteOfDay: Int,
        startMinute: Int,
        endMinute: Int,
    ): Boolean {
        val minute = minuteOfDay.coerceIn(0, NewsNotificationConfig.MINUTES_PER_DAY - 1)
        val start = startMinute.coerceIn(0, NewsNotificationConfig.MINUTES_PER_DAY - 1)
        val end = endMinute.coerceIn(0, NewsNotificationConfig.MINUTES_PER_DAY - 1)
        if (start == end) return false
        return if (start < end) {
            minute in start until end
        } else {
            minute >= start || minute < end
        }
    }

    private const val MAX_KNOWN_IDS = 500
}
