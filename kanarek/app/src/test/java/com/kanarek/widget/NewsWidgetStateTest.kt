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
                items =
                    listOf(
                        NewsItem(
                            title = "Zażółć | test",
                            link = "https://example.com/story",
                            summary = "Line one\nLine two",
                            imageUrl = "https://example.com/image.jpg",
                            source = "Źródło",
                            publishedAtMillis = 123L,
                        ),
                    ),
                lastUpdatedMillis = 456L,
            )

        assertEquals(snapshot, NewsWidgetSnapshotCodec.decode(NewsWidgetSnapshotCodec.encode(snapshot)))
    }

    @Test
    fun corruptSnapshotIsIgnored() {
        assertNull(NewsWidgetSnapshotCodec.decode("broken"))
    }
}
