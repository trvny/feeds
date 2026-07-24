package com.kanarek.widget

import com.kanarek.data.NewsItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NewsWidgetStateTest {
    @Test
    fun migrationCopiesGlobalDefaultsOnlyWhenWidgetHasNoConfig() {
        val global =
            NewsWidgetConfig(
                feeds = listOf("https://example.com/global.xml"),
                headlines = true,
                intervalSeconds = 15,
            )
        val stored =
            NewsWidgetConfig(
                feeds = listOf("https://example.com/widget.xml"),
                headlines = false,
                intervalSeconds = 7,
            )

        assertEquals(global, NewsWidgetConfigs.migrate(null, global))
        assertEquals(stored, NewsWidgetConfigs.migrate(stored, global))
    }

    @Test
    fun configNormalizationTrimsDeduplicatesAndBoundsValues() {
        val normalized =
            NewsWidgetConfigs.normalize(
                config =
                    NewsWidgetConfig(
                        feeds = listOf(" https://example.com/feed ", "https://example.com/feed"),
                        headlines = false,
                        intervalSeconds = 999,
                    ),
                fallbackFeeds = listOf("https://example.com/fallback"),
            )

        assertEquals(listOf("https://example.com/feed"), normalized.feeds)
        assertEquals(120, normalized.intervalSeconds)
    }

    @Test
    fun configNormalizationRestoresFallbackFeeds() {
        val normalized =
            NewsWidgetConfigs.normalize(
                config =
                    NewsWidgetConfig(
                        feeds = listOf(" ", ""),
                        headlines = false,
                        intervalSeconds = 1,
                    ),
                fallbackFeeds = listOf(" https://example.com/fallback "),
            )

        assertEquals(listOf("https://example.com/fallback"), normalized.feeds)
        assertEquals(3, normalized.intervalSeconds)
    }

    @Test
    fun snapshotCodecRoundTripsLastGoodItems() {
        val snapshot =
            NewsWidgetSnapshot(
                items = listOf(item("Zażółć | test")),
                lastUpdatedMillis = 456L,
            )

        assertEquals(snapshot, NewsWidgetSnapshotCodec.decode(NewsWidgetSnapshotCodec.encode(snapshot)))
    }

    @Test
    fun sharedSnapshotCodecPreservesFeedBucketsIncludingEmptyOnes() {
        val snapshot =
            SharedNewsWidgetSnapshot(
                itemsByFeed =
                    linkedMapOf(
                        "https://example.com/a.xml" to listOf(item("A")),
                        "https://example.com/empty.xml" to emptyList(),
                    ),
                lastUpdatedMillis = 789L,
            )

        assertEquals(
            snapshot,
            SharedNewsWidgetSnapshotCodec.decode(SharedNewsWidgetSnapshotCodec.encode(snapshot)),
        )
    }

    @Test
    fun corruptSnapshotIsIgnored() {
        assertNull(NewsWidgetSnapshotCodec.decode("broken"))
        assertNull(SharedNewsWidgetSnapshotCodec.decode("broken"))
    }

    private fun item(title: String): NewsItem =
        NewsItem(
            title = title,
            link = "https://example.com/${title.hashCode()}",
            summary = "Line one\nLine two",
            imageUrl = "https://example.com/image.jpg",
            source = "Źródło",
            publishedAtMillis = 123L,
        )
}
