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
    fun codecPreservesFeedBucketsAndPerFeedFreshness() {
        val snapshot =
            ReaderFeedSnapshot(
                itemsByFeed =
                    linkedMapOf(
                        FEED_A to listOf(item("A", 2L)),
                        FEED_B to emptyList(),
                    ),
                lastUpdatedMillis = 20L,
                updatedAtByFeed = mapOf(FEED_A to 20L, FEED_B to 10L),
            )

        assertEquals(snapshot, ReaderFeedSnapshotCodec.decode(ReaderFeedSnapshotCodec.encode(snapshot)))
    }

    @Test
    fun legacyCodecUsesGlobalTimestampForEveryFeed() {
        val snapshot =
            ReaderFeedSnapshot(
                itemsByFeed =
                    linkedMapOf(
                        FEED_A to listOf(item("A", 2L)),
                        FEED_B to emptyList(),
                    ),
                lastUpdatedMillis = 20L,
                updatedAtByFeed = mapOf(FEED_A to 20L, FEED_B to 10L),
            )
        val legacy =
            ReaderFeedSnapshotCodec
                .encode(snapshot)
                .lineSequence()
                .mapIndexed { index, line ->
                    if (index == 0) {
                        line.replaceFirst("2|", "1|")
                    } else {
                        val fields = line.split('|', limit = 3)
                        "${fields[0]}|${fields[2]}"
                    }
                }.joinToString("\n")

        val decoded = ReaderFeedSnapshotCodec.decode(legacy)

        assertEquals(mapOf(FEED_A to 20L, FEED_B to 20L), decoded?.updatedAtByFeed)
    }

    @Test
    fun corruptSnapshotIsIgnored() {
        assertNull(ReaderFeedSnapshotCodec.decode("broken"))
    }

    @Test
    fun partialFailureUpdatesOneFeedAndKeepsOtherFeedsFreshness() {
        val previous =
            ReaderFeedSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("old-a", 1L)),
                        FEED_B to listOf(item("old-b", 2L)),
                    ),
                lastUpdatedMillis = 5L,
                updatedAtByFeed = mapOf(FEED_A to 5L, FEED_B to 4L),
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
        assertEquals(mapOf(FEED_A to 10L, FEED_B to 4L), outcome.snapshot?.updatedAtByFeed)
        assertFalse(outcome.shouldRetry)
    }

    @Test
    fun unrequestedRetainedFeedSurvivesAnotherFeedsRefresh() {
        val previous =
            ReaderFeedSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("old-a", 1L)),
                        FEED_B to listOf(item("old-b", 1L)),
                    ),
                lastUpdatedMillis = 5L,
                updatedAtByFeed = mapOf(FEED_A to 5L, FEED_B to 4L),
            )

        val outcome =
            mergeReaderFeedSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A, FEED_B),
                results = listOf(ReaderFeedResult(FEED_A, listOf(item("new-a", 2L)), true)),
                nowMillis = 10L,
            )

        assertEquals(listOf("new-a"), outcome.snapshot?.itemsByFeed?.get(FEED_A)?.map(NewsItem::title))
        assertEquals(listOf("old-b"), outcome.snapshot?.itemsByFeed?.get(FEED_B)?.map(NewsItem::title))
        assertEquals(4L, outcome.snapshot?.updatedAtByFeed?.get(FEED_B))
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
    fun emptySuccessKeepsStoriesButRefreshesFeedTimestamp() {
        val previous = ReaderFeedSnapshot(mapOf(FEED_A to listOf(item("old", 1L))), 5L)

        val outcome =
            mergeReaderFeedSnapshot(
                previous = previous,
                activeFeeds = listOf(FEED_A),
                results = listOf(ReaderFeedResult(FEED_A, emptyList(), successful = true)),
                nowMillis = 10L,
            )

        assertEquals(previous.itemsByFeed, outcome.snapshot?.itemsByFeed)
        assertEquals(10L, outcome.snapshot?.updatedAtByFeed?.get(FEED_A))
        assertFalse(outcome.shouldRetry)
    }

    @Test
    fun freshnessIsCalculatedPerFeed() {
        val snapshot =
            ReaderFeedSnapshot(
                itemsByFeed =
                    mapOf(
                        FEED_A to listOf(item("a", 1L)),
                        FEED_B to listOf(item("b", 1L)),
                    ),
                lastUpdatedMillis = 100L,
                updatedAtByFeed = mapOf(FEED_A to 100L, FEED_B to 40L),
            )

        assertEquals(
            setOf(FEED_A),
            freshReaderFeeds(
                snapshot = snapshot,
                feeds = listOf(FEED_A, FEED_B),
                nowMillis = 120L,
                maxAgeMillis = 50L,
            ),
        )
        assertTrue(
            freshReaderFeeds(
                snapshot = snapshot,
                feeds = listOf(FEED_A),
                nowMillis = 120L,
                maxAgeMillis = 0L,
            ).isEmpty(),
        )
    }

    @Test
    fun cachedFeedMakesNotificationResultRecordableWithoutNetworkSuccess() {
        val cached =
            ReaderFeedSyncResult(
                items = listOf(item("cached", 1L)),
                recordableItems = listOf(item("cached", 1L)),
                successfulFeeds = emptySet(),
                cachedFeeds = setOf(FEED_A),
                failedFeeds = setOf(FEED_B),
            )
        val failed =
            ReaderFeedSyncResult(
                items = listOf(item("old", 1L)),
                recordableItems = emptyList(),
                successfulFeeds = emptySet(),
                cachedFeeds = emptySet(),
                failedFeeds = setOf(FEED_A),
            )

        assertTrue(cached.canRecord)
        assertFalse(cached.shouldRetry)
        assertFalse(failed.canRecord)
        assertTrue(failed.shouldRetry)
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
        assertEquals(setOf(FEED_A), outcome.snapshot?.updatedAtByFeed?.keys)
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
