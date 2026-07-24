package com.kanarek.widget

import com.kanarek.data.NewsItem
import com.kanarek.data.NewsMerge
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

internal enum class WidgetRefreshScheduleAction { ENSURE, CANCEL }

internal object WidgetRefreshPolicy {
    fun scheduleAction(activeWidgetIds: IntArray): WidgetRefreshScheduleAction =
        if (activeWidgetIds.isEmpty()) {
            WidgetRefreshScheduleAction.CANCEL
        } else {
            WidgetRefreshScheduleAction.ENSURE
        }

    fun selectTargets(
        requestedWidgetIds: IntArray?,
        activeWidgetIds: IntArray,
    ): IntArray {
        val active = activeWidgetIds.toSet()
        return (requestedWidgetIds ?: activeWidgetIds)
            .asSequence()
            .filter(active::contains)
            .distinct()
            .toList()
            .toIntArray()
    }
}

internal data class FeedRefreshResult(
    val feed: String,
    val items: List<NewsItem>,
    val successful: Boolean,
)

internal data class SharedWidgetRefreshOutcome(
    val snapshot: SharedNewsWidgetSnapshot?,
    val successfulFeeds: Set<String>,
    val failedFeeds: Set<String>,
) {
    val shouldRetry: Boolean
        get() = successfulFeeds.isEmpty() && failedFeeds.isNotEmpty()
}

internal fun widgetFeedUnion(configs: Collection<NewsWidgetConfig>): List<String> =
    configs
        .asSequence()
        .flatMap { it.feeds.asSequence() }
        .map(String::trim)
        .filter(String::isNotEmpty)
        .distinct()
        .toList()

internal fun mergeSharedWidgetSnapshot(
    previous: SharedNewsWidgetSnapshot?,
    activeFeeds: List<String>,
    results: List<FeedRefreshResult>,
    nowMillis: Long,
): SharedWidgetRefreshOutcome {
    val feeds = activeFeeds.map(String::trim).filter(String::isNotEmpty).distinct()
    if (feeds.isEmpty()) {
        return SharedWidgetRefreshOutcome(null, emptySet(), emptySet())
    }
    val active = feeds.toSet()
    val byFeed = results.filter { it.feed in active }.associateBy(FeedRefreshResult::feed)
    val successfulFeeds = byFeed.values.filter(FeedRefreshResult::successful).mapTo(linkedSetOf(), FeedRefreshResult::feed)
    val failedFeeds = byFeed.values.filterNot(FeedRefreshResult::successful).mapTo(linkedSetOf(), FeedRefreshResult::feed)
    val merged = linkedMapOf<String, List<NewsItem>>()

    feeds.forEach { feed ->
        val result = byFeed[feed]
        when {
            result?.successful == true -> merged[feed] = result.items.distinctBy { it.link.trim() }
            previous?.itemsByFeed?.containsKey(feed) == true -> merged[feed] = previous.itemsByFeed.getValue(feed)
        }
    }
    val updated =
        if (successfulFeeds.isNotEmpty()) {
            nowMillis
        } else {
            previous?.lastUpdatedMillis
        }
    return SharedWidgetRefreshOutcome(
        snapshot = updated?.let { SharedNewsWidgetSnapshot(merged, it) },
        successfulFeeds = successfulFeeds,
        failedFeeds = failedFeeds,
    )
}

internal fun itemsForWidget(
    shared: SharedNewsWidgetSnapshot?,
    config: NewsWidgetConfig,
    legacy: NewsWidgetSnapshot?,
    perSourceCap: Int,
    limit: Int,
): List<NewsItem> {
    val feeds = config.feeds.map(String::trim).filter(String::isNotEmpty).distinct()
    val sharedItems = feeds.flatMap { shared?.itemsByFeed?.get(it).orEmpty() }
    val hasCompleteSharedCoverage = shared != null && feeds.all(shared.itemsByFeed::containsKey)
    val combined =
        buildList {
            addAll(sharedItems)
            if (!hasCompleteSharedCoverage) addAll(legacy?.items.orEmpty())
        }.distinctBy { it.link.trim() }
    return NewsMerge.capPerSource(combined, perSourceCap).take(limit)
}

internal class WidgetRefreshSingleFlight {
    private val mutex = Mutex()

    suspend fun <T> run(block: suspend () -> T): T = mutex.withLock { block() }
}
