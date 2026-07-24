package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReaderFeedSnapshotTest {
    @Test
    fun refreshIntervalsNormalizeAndChooseScheduleAction() {
        assertEquals(ReaderBackgroundRefresh.OFF, ReaderBackgroundRefresh.normalize(17))
        assertEquals(
            ReaderRefreshScheduleAction.CANCEL,
            ReaderBackgroundRefresh.scheduleAction(ReaderBackgroundRefresh.OFF),
        )
        ReaderBackgroundRefresh.options.drop(1).forEach { minutes ->
            assertEquals(minutes, ReaderBackgroundRefresh.normalize(minutes))
            assertEquals(
                ReaderRefreshScheduleAction.SCHEDULE,
                ReaderBackgroundRefresh.scheduleAction(minutes),
            )
        }
    }

    @Test
    fun codecPreservesFeedBucketsIncludingEmptyOnes() {
        val snapshot =
            ReaderFeedSnapshot(
                itemsByFeed =
                    linkedMapOf(
                        FEED_A to listOf(item("A", 2L)),
                        FEED_B to emptyList(),
                    ),
                lastUpdatedMillis = 10L,
            )

        assertEquals(snapshot, ReaderFeedSnapshotCodec.decode(ReaderFeedSnapshotCodec.encode(snapshot)))
    }

    @Test
    fun corruptSnapshotIsIgnored() {
        assertNull(ReaderFeedSnapshotCodec.decode("broken"))
    }

    @Test
    fun partialFailureUpdatesOneFeedAndKeepsLastGoodOtherFeed() {
        val previous =
            ReaderFeedSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("old-a", 1L)),
                        FEED_B to listOf(item("old-b", 2L)),
                    ),
                lastUpdatedMillis = 5L,
            )

        val outcome =
            mergeReaderFeedSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A, FEED_B),
                results =
                    listOf(
                        ReaderFeedResult(FEED_A, listOf(item("new-a", 3L)), successful = true),
                        ReaderFeedResult(FEED_B, emptyList(), successful = false),
                    ),
                nowMillis = 10L,
            )

        assertEquals(listOf("new-a"), outcome.snapshot?.itemsByFeed?.get(FEED_A)?.map(NewsItem::title))
        assertEquals(listOf("old-b"), outcome.snapshot?.itemsByFeed?.get(FEED_B)?.map(NewsItem::title))
        assertFalse(outcome.shouldRetry)
    }

    @Test
    fun totalFailureKeepsSnapshotAndRequestsRetry() {
        val previous = ReaderFeedSnapshot(mapOf(FEED_A to listOf(item("old", 1L))), 5L)

        val outcome =
            mergeReaderFeedSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A),
                results = listOf(ReaderFeedResult(FEED_A, emptyList(), successful = false)),
                nowMillis = 10L,
            )

        assertEquals(previous, outcome.snapshot)
        assertTrue(outcome.shouldRetry)
    }

    @Test
    fun emptySuccessDoesNotErasePreviousStoriesOrRetry() {
        val previous = ReaderFeedSnapshot(mapOf(FEED_A to listOf(item("old", 1L))), 5L)

        val outcome =
            mergeReaderFeedSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A),
                results = listOf(ReaderFeedResult(FEED_A, emptyList(), successful = true)),
                nowMillis = 10L,
            )

        assertEquals(previous.itemsByFeed, outcome.snapshot?.itemsByFeed)
        assertFalse(outcome.shouldRetry)
    }

    @Test
    fun readerUsesOnlyConfiguredFeedsAndAppliesSourceCap() {
        val snapshot =
            ReaderFeedSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("a1", 3L), item("a2", 2L)),
                        FEED_B to listOf(item("b", 1L)),
                    ),
                lastUpdatedMillis = 10L,
            )

        val items = readerItems(snapshot, listOf(FEED_A), perSourceCap = 1, limit = 15)

        assertEquals(listOf("a1"), items.map(NewsItem::title))
    }

    @Test
    fun removedFeedsDisappearFromNewSnapshot() {
        val previous =
            ReaderFeedSnapshot(
                mapOf(
                    FEED_A to listOf(item("a", 1L)),
                    FEED_B to listOf(item("b", 1L)),
                ),
                5L,
            )

        val outcome =
            mergeReaderFeedSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A),
                results = emptyList(),
                nowMillis = 10L,
            )

        assertEquals(setOf(FEED_A), outcome.snapshot?.itemsByFeed?.keys)
    }

    private fun item(
        title: String,
        publishedAtMillis: Long,
    ): NewsItem =
        NewsItem(
            title = title,
            link = "https://example.com/$title",
            summary = "Summary: ~ | unicode żółć",
            imageUrl = null,
            source = "Example",
            publishedAtMillis = publishedAtMillis,
        )

    companion object {
        private const val FEED_A = "https://example.com/a.xml"
        private const val FEED_B = "https://example.com/b.xml"
    }
}
