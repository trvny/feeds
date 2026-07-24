package com.kanarek.ui

import com.kanarek.data.ArticleListFilter
import com.kanarek.data.NewsItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ReaderStateRestorationTest {
    @Test
    fun `article preview survives state restoration`() {
        val article =
            NewsItem(
                title = "Title",
                link = "https://example.com/article",
                summary = "Summary",
                imageUrl = "https://example.com/image.jpg",
                source = "Example",
                publishedAtMillis = 1234L,
            )
        val restored = restoreReaderNavigationState(ReaderNavigationState().openArticle(article).toSavedBundle())

        assertEquals(ReaderRoute.ARTICLE, restored.route)
        assertEquals(article, restored.selectedArticle)
    }

    @Test
    fun `nested settings route survives state restoration`() {
        val restored =
            restoreReaderNavigationState(
                ReaderNavigationState().open(ReaderRoute.NOTIFICATIONS).toSavedBundle(),
            )

        assertEquals(ReaderRoute.NOTIFICATIONS, restored.route)
        assertNull(restored.selectedArticle)
    }

    @Test
    fun `search and source filters survive state restoration`() {
        val state =
            ReaderFilterState(
                filter = ArticleListFilter.SAVED,
                query = "space",
                sources = setOf("PAP", "Reuters"),
            )
        val restored = restoreReaderFilterState(state.toSavedBundle())

        assertEquals(state, restored)
    }

    @Test
    fun `article route without an article falls back to Reader`() {
        val saved = ReaderNavigationState(route = ReaderRoute.ARTICLE).toSavedBundle()
        val restored = restoreReaderNavigationState(saved)

        assertEquals(ReaderNavigationState(), restored)
    }
}
