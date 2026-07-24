package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NewsNotificationsTest {
    @Test
    fun firstSyncSeedsIdsWithoutNotification() {
        val first = item("https://example.com/first")
        val second = item("https://example.com/second")

        val decision =
            NewsNotifications.evaluate(
                NewsNotificationSnapshot(
                    currentItems = listOf(first, second),
                    knownIds = emptySet(),
                    initialized = false,
                    minuteOfDay = 12 * 60,
                    config = NewsNotificationConfig(enabled = true, quietHoursEnabled = false),
                ),
            )

        assertEquals(emptyList<NewsItem>(), decision.newItems)
        assertEquals(
            setOf(NewsNotifications.stableId(first), NewsNotifications.stableId(second)),
            decision.knownIds,
        )
        assertFalse(decision.shouldNotify)
    }

    @Test
    fun laterSyncNotifiesOnlyPreviouslyUnknownStableIds() {
        val known = item("https://example.com/known")
        val fresh = item("https://example.com/fresh")

        val decision =
            NewsNotifications.evaluate(
                NewsNotificationSnapshot(
                    currentItems = listOf(fresh, known, fresh),
                    knownIds = setOf(NewsNotifications.stableId(known)),
                    initialized = true,
                    minuteOfDay = 12 * 60,
                    config = NewsNotificationConfig(enabled = true, quietHoursEnabled = false),
                ),
            )

        assertEquals(listOf(fresh), decision.newItems)
        assertEquals(
            setOf(NewsNotifications.stableId(fresh), NewsNotifications.stableId(known)),
            decision.knownIds,
        )
        assertTrue(decision.shouldNotify)
    }

    @Test
    fun successfulEmptyBaselineLetsFirstLaterStoryNotify() {
        val config = NewsNotificationConfig(enabled = true, quietHoursEnabled = false)
        val emptyBaseline =
            NewsNotifications.evaluate(
                NewsNotificationSnapshot(
                    currentItems = emptyList(),
                    knownIds = emptySet(),
                    initialized = false,
                    minuteOfDay = 12 * 60,
                    config = config,
                ),
            )
        val firstStory = item("https://example.com/first-after-empty")
        val next =
            NewsNotifications.evaluate(
                NewsNotificationSnapshot(
                    currentItems = listOf(firstStory),
                    knownIds = emptyBaseline.knownIds,
                    initialized = true,
                    minuteOfDay = 13 * 60,
                    config = config,
                ),
            )

        assertFalse(emptyBaseline.shouldNotify)
        assertEquals(listOf(firstStory), next.newItems)
        assertTrue(next.shouldNotify)
    }

    @Test
    fun failedEmptyPollIsNotRecordedButSuccessfulEmptyPollIs() {
        assertFalse(
            NewsNotificationPolling.shouldRecord(
                NewsFetchResult(items = emptyList(), successfulSources = 0),
            ),
        )
        assertTrue(
            NewsNotificationPolling.shouldRecord(
                NewsFetchResult(items = emptyList(), successfulSources = 1),
            ),
        )
    }

    @Test
    fun pollingBatchesCoverEverySelectedFeed() {
        val feeds = (1..25).map { "https://feeds.example/$it" }

        val batches = NewsNotificationPolling.feedBatches(feeds, maxFeedsPerBatch = 12)

        assertEquals(listOf(12, 12, 1), batches.map(List<String>::size))
        assertEquals(feeds, batches.flatten())
    }

    @Test
    fun pollingCombinesResultsFromLaterBatches() {
        val older = item("https://example.com/older", publishedAtMillis = 1L)
        val newer = item("https://example.com/newer", publishedAtMillis = 2L)

        val combined =
            NewsNotificationPolling.combine(
                results =
                    listOf(
                        NewsFetchResult(listOf(older), successfulSources = 12),
                        NewsFetchResult(listOf(newer), successfulSources = 1),
                    ),
                limit = 100,
            )

        assertEquals(listOf(newer, older), combined.items)
        assertEquals(13, combined.successfulSources)
    }

    @Test
    fun quietHoursWrapAcrossMidnight() {
        assertTrue(NewsNotifications.isQuietTime(23 * 60, 22 * 60, 7 * 60))
        assertTrue(NewsNotifications.isQuietTime(6 * 60 + 59, 22 * 60, 7 * 60))
        assertFalse(NewsNotifications.isQuietTime(7 * 60, 22 * 60, 7 * 60))
        assertFalse(NewsNotifications.isQuietTime(12 * 60, 22 * 60, 7 * 60))
        assertFalse(NewsNotifications.isQuietTime(12 * 60, 12 * 60, 12 * 60))
    }

    @Test
    fun quietCycleMarksItemsSeenWithoutCreatingBacklog() {
        val fresh = item("https://example.com/night")
        val quietConfig = NewsNotificationConfig(enabled = true)
        val quietDecision =
            NewsNotifications.evaluate(
                NewsNotificationSnapshot(
                    currentItems = listOf(fresh),
                    knownIds = emptySet(),
                    initialized = true,
                    minuteOfDay = 23 * 60,
                    config = quietConfig,
                ),
            )
        val morningDecision =
            NewsNotifications.evaluate(
                NewsNotificationSnapshot(
                    currentItems = listOf(fresh),
                    knownIds = quietDecision.knownIds,
                    initialized = true,
                    minuteOfDay = 8 * 60,
                    config = quietConfig,
                ),
            )

        assertEquals(listOf(fresh), quietDecision.newItems)
        assertFalse(quietDecision.shouldNotify)
        assertEquals(emptyList<NewsItem>(), morningDecision.newItems)
        assertFalse(morningDecision.shouldNotify)
    }

    @Test
    fun seenHistoryKeepsCurrentItemsWithinBound() {
        val current = (1..4).map { item("https://example.com/$it") }

        val decision =
            NewsNotifications.evaluate(
                snapshot =
                    NewsNotificationSnapshot(
                        currentItems = current,
                        knownIds = setOf("old"),
                        initialized = true,
                        minuteOfDay = 12 * 60,
                        config = NewsNotificationConfig(enabled = true, quietHoursEnabled = false),
                    ),
                maxKnownIds = 3,
            )

        assertEquals(
            current.take(3).mapTo(linkedSetOf(), NewsNotifications::stableId),
            decision.knownIds,
        )
    }

    @Test
    fun allSourcesSelectionTracksAddedAndRemovedConfiguredFeeds() {
        val config =
            NewsNotificationConfig(
                enabled = true,
                selectedFeeds = listOf("https://feeds.example/a", "https://feeds.example/b"),
                configuredFeeds = listOf("https://feeds.example/a", "https://feeds.example/b"),
            )

        val reconciled =
            config.reconciledWith(
                listOf("https://feeds.example/b", "https://feeds.example/c"),
            )

        assertEquals(
            listOf("https://feeds.example/b", "https://feeds.example/c"),
            reconciled.selectedFeeds,
        )
        assertEquals(reconciled.selectedFeeds, reconciled.configuredFeeds)
    }

    @Test
    fun intentionalSourceSubsetDoesNotSelectNewFeeds() {
        val config =
            NewsNotificationConfig(
                enabled = true,
                selectedFeeds = listOf("https://feeds.example/a"),
                configuredFeeds = listOf("https://feeds.example/a", "https://feeds.example/b"),
            )

        val reconciled =
            config.reconciledWith(
                listOf(
                    "https://feeds.example/a",
                    "https://feeds.example/b",
                    "https://feeds.example/c",
                ),
            )

        assertEquals(listOf("https://feeds.example/a"), reconciled.selectedFeeds)
    }

    @Test
    fun deletedOnlySelectionFallsBackToConfiguredFeeds() {
        val config =
            NewsNotificationConfig(
                enabled = true,
                selectedFeeds = listOf("https://feeds.example/deleted"),
                configuredFeeds =
                    listOf(
                        "https://feeds.example/deleted",
                        "https://feeds.example/also-deleted",
                    ),
            )

        val reconciled =
            config.reconciledWith(listOf("https://feeds.example/current"))

        assertEquals(listOf("https://feeds.example/current"), reconciled.selectedFeeds)
    }

    private fun item(
        link: String,
        publishedAtMillis: Long? = null,
    ): NewsItem =
        NewsItem(
            title = link.substringAfterLast('/'),
            link = link,
            summary = "",
            imageUrl = null,
            source = "Example",
            publishedAtMillis = publishedAtMillis,
        )
}
