package com.kanarek.widget

import com.kanarek.data.NewsItem
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class WidgetRefreshCoordinatorTest {
    @Test
    fun scheduleFollowsWidgetLifecycle() {
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(intArrayOf(1)),
        )
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(intArrayOf(1, 2)),
        )
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(intArrayOf(2)),
        )
        assertEquals(
            WidgetRefreshScheduleAction.CANCEL,
            WidgetRefreshPolicy.scheduleAction(intArrayOf()),
        )
    }

    @Test
    fun manualTargetsAreActiveAndDeduplicated() {
        assertEquals(
            listOf(2),
            WidgetRefreshPolicy
                .selectTargets(
                    requestedWidgetIds = intArrayOf(2, 2, 3),
                    activeWidgetIds = intArrayOf(1, 2),
                ).toList(),
        )
    }

    @Test
    fun feedUnionPreservesOrderAndRemovesDuplicates() {
        val configs =
            listOf(
                config(" https://example.com/a.xml ", "https://example.com/b.xml"),
                config("https://example.com/b.xml", "https://example.com/c.xml"),
            )

        assertEquals(
            listOf(
                "https://example.com/a.xml",
                "https://example.com/b.xml",
                "https://example.com/c.xml",
            ),
            widgetFeedUnion(configs),
        )
    }

    @Test
    fun partialFailureUpdatesSuccessfulFeedAndPreservesFailedFeed() {
        val previous =
            SharedNewsWidgetSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("old-a", 1L)),
                        FEED_B to listOf(item("old-b", 2L)),
                    ),
                lastUpdatedMillis = 10L,
            )

        val outcome =
            mergeSharedWidgetSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A, FEED_B),
                results =
                    listOf(
                        FeedRefreshResult(FEED_A, listOf(item("new-a", 3L)), successful = true),
                        FeedRefreshResult(FEED_B, emptyList(), successful = false),
                    ),
                nowMillis = 20L,
            )

        assertEquals(listOf("new-a"), outcome.snapshot?.itemsByFeed?.get(FEED_A)?.map(NewsItem::title))
        assertEquals(listOf("old-b"), outcome.snapshot?.itemsByFeed?.get(FEED_B)?.map(NewsItem::title))
        assertEquals(20L, outcome.snapshot?.lastUpdatedMillis)
        assertFalse(outcome.shouldRetry)
    }

    @Test
    fun totalFailurePreservesLastGoodDataAndTimestamp() {
        val previous =
            SharedNewsWidgetSnapshot(
                itemsByFeed = mapOf(FEED_A to listOf(item("old", 1L))),
                lastUpdatedMillis = 10L,
            )

        val outcome =
            mergeSharedWidgetSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A),
                results = listOf(FeedRefreshResult(FEED_A, emptyList(), successful = false)),
                nowMillis = 20L,
            )

        assertEquals(previous, outcome.snapshot)
        assertTrue(outcome.shouldRetry)
    }

    @Test
    fun emptySuccessfulFeedIsCoveredWithoutRetry() {
        val outcome =
            mergeSharedWidgetSnapshot(
                previous = null,
                activeFeeds = listOf(FEED_A),
                results = listOf(FeedRefreshResult(FEED_A, emptyList(), successful = true)),
                nowMillis = 20L,
            )

        assertEquals(emptyList<NewsItem>(), outcome.snapshot?.itemsByFeed?.get(FEED_A))
        assertEquals(20L, outcome.snapshot?.lastUpdatedMillis)
        assertFalse(outcome.shouldRetry)
    }

    @Test
    fun deletedWidgetFeedsAreRemovedBeforeCommit() {
        val previous =
            SharedNewsWidgetSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("a", 1L)),
                        FEED_B to listOf(item("b", 2L)),
                    ),
                lastUpdatedMillis = 10L,
            )

        val outcome =
            mergeSharedWidgetSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A),
                results = listOf(FeedRefreshResult(FEED_B, listOf(item("new-b", 3L)), successful = true)),
                nowMillis = 20L,
            )

        assertEquals(setOf(FEED_A), outcome.snapshot?.itemsByFeed?.keys)
        assertEquals(10L, outcome.snapshot?.lastUpdatedMillis)
    }

    @Test
    fun noActiveFeedsProducesNoSnapshot() {
        val outcome =
            mergeSharedWidgetSnapshot(
                previous = SharedNewsWidgetSnapshot(mapOf(FEED_A to emptyList()), 10L),
                activeFeeds = emptyList(),
                results = emptyList(),
                nowMillis = 20L,
            )

        assertNull(outcome.snapshot)
    }

    @Test
    fun widgetsFilterTheSharedSnapshotByTheirOwnFeeds() {
        val shared =
            SharedNewsWidgetSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("a", 2L)),
                        FEED_B to listOf(item("b", 1L)),
                    ),
                lastUpdatedMillis = 10L,
            )

        assertEquals(
            listOf("a"),
            itemsForWidget(shared, config(FEED_A), null, perSourceCap = 0, limit = 12)
                .map(NewsItem::title),
        )
        assertEquals(
            listOf("b"),
            itemsForWidget(shared, config(FEED_B), null, perSourceCap = 0, limit = 12)
                .map(NewsItem::title),
        )
    }

    @Test
    fun legacySnapshotIsUsedOnlyUntilSharedCoverageIsComplete() {
        val legacy = NewsWidgetSnapshot(listOf(item("legacy", 1L)), 5L)
        val partial = SharedNewsWidgetSnapshot(mapOf(FEED_A to listOf(item("a", 3L))), 10L)
        val complete =
            SharedNewsWidgetSnapshot(
                mapOf(
                    FEED_A to listOf(item("a", 3L)),
                    FEED_B to emptyList(),
                ),
                10L,
            )
        val widgetConfig = config(FEED_A, FEED_B)

        assertEquals(
            listOf("a", "legacy"),
            itemsForWidget(partial, widgetConfig, legacy, 0, 12).map(NewsItem::title),
        )
        assertEquals(
            listOf("a"),
            itemsForWidget(complete, widgetConfig, legacy, 0, 12).map(NewsItem::title),
        )
    }

    @Test
    fun refreshesNeverRunInParallel() =
        runBlocking {
            val gate = WidgetRefreshSingleFlight()
            val firstEntered = CompletableDeferred<Unit>()
            val releaseFirst = CompletableDeferred<Unit>()
            val secondEntered = CompletableDeferred<Unit>()
            val active = AtomicInteger(0)
            val maximumActive = AtomicInteger(0)

            suspend fun recordRefresh(
                entered: CompletableDeferred<Unit>,
                release: CompletableDeferred<Unit>? = null,
            ) {
                val current = active.incrementAndGet()
                maximumActive.updateAndGet { previous -> maxOf(previous, current) }
                entered.complete(Unit)
                release?.await()
                active.decrementAndGet()
            }

            val first =
                async(Dispatchers.Default) {
                    gate.run { recordRefresh(firstEntered, releaseFirst) }
                }
            firstEntered.await()
            val second =
                async(Dispatchers.Default) {
                    gate.run { recordRefresh(secondEntered) }
                }
            yield()

            assertFalse(secondEntered.isCompleted)
            releaseFirst.complete(Unit)
            first.await()
            second.await()
            assertEquals(1, maximumActive.get())
        }

    private fun config(vararg feeds: String): NewsWidgetConfig =
        NewsWidgetConfig(feeds.toList(), headlines = false, intervalSeconds = 10)

    private fun item(
        title: String,
        publishedAtMillis: Long,
    ): NewsItem =
        NewsItem(
            title = title,
            link = "https://example.com/$title",
            summary = "",
            imageUrl = null,
            source = "Example",
            publishedAtMillis = publishedAtMillis,
        )

    companion object {
        private const val FEED_A = "https://example.com/a.xml"
        private const val FEED_B = "https://example.com/b.xml"
    }
}
