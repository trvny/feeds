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
)

internal data class ReaderFeedSyncResult(
    val items: List<NewsItem>,
    val successfulFeeds: Set<String>,
    val failedFeeds: Set<String>,
) {
    val shouldRetry: Boolean
        get() = successfulFeeds.isEmpty() && failedFeeds.isNotEmpty()
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
    ): ReaderFeedSyncResult =
        singleFlight.withLock {
            val feeds = config.feeds.normalizeFeedUrls()
            if (feeds.isEmpty()) {
                store.clear()
                return@withLock ReaderFeedSyncResult(emptyList(), emptySet(), emptySet())
            }
            val previous = store.snapshot()
            val results = fetchFeeds(feeds, config.backendUrl)
            val outcome =
                mergeReaderFeedSnapshot(
                    previous = previous,
                    activeFeeds = feeds,
                    results = results,
                    nowMillis = System.currentTimeMillis(),
                )
            outcome.snapshot?.let(store::save)
            ReaderFeedSyncResult(
                items =
                    readerItems(
                        snapshot = outcome.snapshot,
                        feeds = feeds,
                        perSourceCap = config.perSourceCap,
                        limit = limit,
                    ),
                successfulFeeds = outcome.successfulFeeds,
                failedFeeds = outcome.failedFeeds,
            )
        }

    private suspend fun fetchFeeds(
        feeds: List<String>,
        backendUrl: String,
    ): List<ReaderFeedResult> =
        coroutineScope {
            feeds.map { feed ->
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

    companion object {
        private const val ITEMS_PER_FEED = 20
        private val singleFlight = Mutex()
    }
}
