package com.kanarek.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

internal data class ReaderFeedSyncConfig(
    val feeds: List<String>,
    val backendUrl: String,
    val perSourceCap: Int,
    val retainedFeeds: List<String> = feeds,
)

internal data class ReaderFeedSyncResult(
    val items: List<NewsItem>,
    val recordableItems: List<NewsItem>,
    val successfulFeeds: Set<String>,
    val cachedFeeds: Set<String>,
    val failedFeeds: Set<String>,
) {
    val canRecord: Boolean
        get() = successfulFeeds.isNotEmpty() || cachedFeeds.isNotEmpty()

    val shouldRetry: Boolean
        get() = !canRecord && failedFeeds.isNotEmpty()
}

internal class ReaderFeedSynchronizer(
    context: Context,
    private val repository: NewsRepository = NewsRepository(),
) {
    private val appContext = context.applicationContext
    private val store = ReaderFeedStore(appContext)
    private val cache = FeedCache(appContext)

    fun cachedItems(
        config: ReaderFeedSyncConfig,
        limit: Int,
    ): List<NewsItem> =
        readerItems(
            snapshot = store.snapshot(),
            feeds = config.feeds,
            perSourceCap = config.perSourceCap,
            limit = limit,
        )

    suspend fun refresh(
        config: ReaderFeedSyncConfig,
        limit: Int,
        maxCacheAgeMillis: Long = 0L,
        nowMillis: Long = System.currentTimeMillis(),
    ): ReaderFeedSyncResult =
        singleFlight.withLock {
            val feeds = config.feeds.normalizeFeedUrls()
            val retainedFeeds = (config.retainedFeeds + feeds).normalizeFeedUrls()
            if (retainedFeeds.isEmpty()) {
                store.clear()
                return@withLock emptyResult()
            }
            val previous = store.snapshot()
            val cachedFeeds =
                freshReaderFeeds(
                    snapshot = previous,
                    feeds = feeds,
                    nowMillis = nowMillis,
                    maxAgeMillis = maxCacheAgeMillis,
                )
            val results =
                fetchFeeds(
                    feeds = feeds.filterNot(cachedFeeds::contains),
                    backendUrl = config.backendUrl,
                )
            val outcome =
                mergeReaderFeedSnapshot(
                    previous = previous,
                    activeFeeds = retainedFeeds,
                    results = results,
                    nowMillis = nowMillis,
                )
            outcome.snapshot?.let(store::save)
            val recordableFeeds = cachedFeeds + outcome.successfulFeeds
            ReaderFeedSyncResult(
                items =
                    readerItems(
                        snapshot = outcome.snapshot,
                        feeds = feeds,
                        perSourceCap = config.perSourceCap,
                        limit = limit,
                    ),
                recordableItems =
                    readerItems(
                        snapshot = outcome.snapshot,
                        feeds = feeds.filter(recordableFeeds::contains),
                        perSourceCap = config.perSourceCap,
                        limit = limit,
                    ),
                successfulFeeds = outcome.successfulFeeds,
                cachedFeeds = cachedFeeds,
                failedFeeds = outcome.failedFeeds,
            )
        }

    private suspend fun fetchFeeds(
        feeds: List<String>,
        backendUrl: String,
    ): List<ReaderFeedResult> =
        coroutineScope {
            feeds
                .map { feed ->
                    async(Dispatchers.IO) {
                        val fetched =
                            runCatching {
                                repository.fetchBlockingWithStatus(
                                    feeds = listOf(feed),
                                    backendUrl = backendUrl,
                                    limit = ITEMS_PER_FEED,
                                    cache = cache,
                                    perSourceCap = 0,
                                )
                            }.getOrDefault(NewsFetchResult(emptyList(), successfulSources = 0))
                        ReaderFeedResult(
                            feed = feed,
                            items = fetched.items,
                            successful = fetched.successfulSources > 0,
                        )
                    }
                }.awaitAll()
        }

    private fun emptyResult(): ReaderFeedSyncResult =
        ReaderFeedSyncResult(
            items = emptyList(),
            recordableItems = emptyList(),
            successfulFeeds = emptySet(),
            cachedFeeds = emptySet(),
            failedFeeds = emptySet(),
        )

    companion object {
        private const val ITEMS_PER_FEED = 20
        private val singleFlight = Mutex()
    }
}
