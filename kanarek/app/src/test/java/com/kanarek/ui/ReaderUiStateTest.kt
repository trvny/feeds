package com.kanarek.ui

import com.kanarek.data.ArticleListFilter
import com.kanarek.data.NewsItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReaderUiStateTest {
    @Test
    fun articleBackReturnsToReaderAndClearsSelection() {
        val article = item("https://example.com/article")

        val opened = ReaderNavigationState().openArticle(article)
        val returned = opened.back()

        assertEquals(ReaderRoute.ARTICLE, opened.route)
        assertEquals(article, opened.selectedArticle)
        assertEquals(ReaderRoute.READER, returned.route)
        assertNull(returned.selectedArticle)
    }

    @Test
    fun nestedSettingsPagesBackToSettingsBeforeReader() {
        val storage = ReaderNavigationState().open(ReaderRoute.STORAGE)
        val notifications = ReaderNavigationState().open(ReaderRoute.NOTIFICATIONS)

        assertEquals(ReaderRoute.SETTINGS, storage.back().route)
        assertEquals(ReaderRoute.SETTINGS, notifications.back().route)
        assertEquals(ReaderRoute.READER, storage.back().back().route)
    }

    @Test
    fun sourceToggleIsCaseInsensitiveAndPreservesCanonicalValue() {
        val selected = ReaderFilterState().toggleSource(" Example ")
        val removed = selected.toggleSource("example")

        assertEquals(setOf("Example"), selected.sources)
        assertTrue(selected.hasSearchFilters)
        assertTrue(removed.sources.isEmpty())
        assertFalse(removed.hasSearchFilters)
    }

    @Test
    fun queryAndArticleFilterRemainIndependent() {
        val state =
            ReaderFilterState(
                filter = ArticleListFilter.SAVED,
                query = "  space  ",
            )

        assertEquals(ArticleListFilter.SAVED, state.filter)
        assertTrue(state.hasSearchFilters)
        assertEquals("  space  ", state.query)
    }

    @Test
    fun sourceOptionsMergeFeedSavedAndSelectedWithoutCaseDuplicates() {
        val options =
            readerSourceOptions(
                feedItems = listOf(item("https://example.com/1", source = "PAP")),
                savedArticles = listOf(item("https://example.com/2", source = "pap")),
                selectedSources = setOf("Reuters"),
            )

        assertEquals(listOf("PAP", "Reuters"), options)
    }

    private fun item(
        link: String,
        source: String = "Example",
    ): NewsItem =
        NewsItem(
            title = link.substringAfterLast('/'),
            link = link,
            summary = "",
            imageUrl = null,
            source = source,
            publishedAtMillis = null,
        )
}
