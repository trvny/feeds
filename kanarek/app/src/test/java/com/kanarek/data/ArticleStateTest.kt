package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ArticleStateTest {
    @Test
    fun savedArticleCodecRoundTrips() {
        val original =
            NewsItem(
                title = "Zażółć gęślą",
                link = "https://example.com/story?x=1|2",
                summary = "Opis z polskimi znakami",
                imageUrl = "https://example.com/image.jpg",
                source = "Źródło",
                publishedAtMillis = 123_456L,
            )

        assertEquals(original, SavedArticleCodec.decode(SavedArticleCodec.encode(original)))
    }

    @Test
    fun corruptSavedRecordsAreIgnored() {
        val valid = item(link = "https://example.com/valid")

        assertEquals(
            listOf(valid),
            SavedArticleCodec.decodeAll(setOf("broken", SavedArticleCodec.encode(valid))),
        )
    }

    @Test
    fun filtersHideHiddenItemsAndKeepSavedSnapshots() {
        val unread = item(link = "https://example.com/unread", publishedAtMillis = 20L)
        val read = item(link = "https://example.com/read", publishedAtMillis = 10L)
        val savedOld = item(link = "https://example.com/saved", publishedAtMillis = 5L)
        val hidden = item(link = "https://example.com/hidden", publishedAtMillis = 30L)
        val state =
            ArticleState(
                readIds = setOf(ArticleStates.id(read)),
                savedArticles = listOf(savedOld, read),
                hiddenIds = setOf(ArticleStates.id(hidden)),
            )
        val feed = listOf(hidden, unread, read, unread)

        assertEquals(listOf(unread, read), ArticleStates.visible(feed, state, ArticleListFilter.ALL))
        assertEquals(listOf(unread), ArticleStates.visible(feed, state, ArticleListFilter.UNREAD))
        assertEquals(listOf(read, savedOld), ArticleStates.visible(feed, state, ArticleListFilter.SAVED))
        assertTrue(state.isRead(read))
        assertFalse(state.isRead(unread))
        assertTrue(state.isSaved(savedOld))
    }

    @Test
    fun articleIdTrimsFeedWhitespace() {
        val article = item(link = "  https://example.com/story  ")

        assertEquals("https://example.com/story", ArticleStates.id(article))
    }

    @Test
    fun articleHistoryDropsOldestAndExpiredRecords() {
        var records = emptySet<String>()
        records = ArticleIdHistory.touch(records, "old", 1_000L, 10_000L, 10)
        records = ArticleIdHistory.touch(records, "middle", 2_000L, 10_000L, 10)
        records = ArticleIdHistory.touch(records, "new", 3_000L, 10_000L, 10)

        val pruned =
            ArticleIdHistory.prune(
                records = records,
                nowMillis = 4_000L,
                maxAgeMillis = 2_500L,
                maxCount = 2,
            )

        assertEquals(setOf("middle", "new"), ArticleIdHistory.ids(pruned))
        assertEquals(2, pruned.size)
    }

    @Test
    fun articleHistoryMigratesLegacyIdsAndRefreshesExistingOnes() {
        val migrated =
            ArticleIdHistory.prune(
                records = setOf("  https://example.com/legacy  "),
                nowMillis = 5_000L,
                maxAgeMillis = 10_000L,
                maxCount = 10,
            )
        val refreshed =
            ArticleIdHistory.touch(
                records = migrated,
                id = "https://example.com/legacy",
                nowMillis = 6_000L,
                maxAgeMillis = 10_000L,
                maxCount = 10,
            )

        assertEquals(setOf("https://example.com/legacy"), ArticleIdHistory.ids(refreshed))
        assertEquals(1, refreshed.size)
        assertTrue(refreshed.single().startsWith("1|"))
    }

    private fun item(
        link: String,
        publishedAtMillis: Long? = null,
    ): NewsItem =
        NewsItem(
            title = "Title",
            link = link,
            summary = "Summary",
            imageUrl = null,
            source = "Source",
            publishedAtMillis = publishedAtMillis,
        )
}
