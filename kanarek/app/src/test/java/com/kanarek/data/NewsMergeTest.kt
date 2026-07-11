package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Test

class NewsMergeTest {
    private fun item(source: String, ms: Long) =
        NewsItem(
            title = "$source@$ms",
            link = "https://example.com/$source/$ms",
            summary = "",
            imageUrl = null,
            source = source,
            publishedAtMillis = ms,
        )

    @Test
    fun capKeepsNewestPerSource() {
        val items =
            listOf(
                item("PAP", 100), item("PAP", 90), item("PAP", 80), item("PAP", 70),
                item("Reuters", 95), item("Reuters", 60),
            )
        val out = NewsMerge.capPerSource(items, 2)
        assertEquals(listOf(100L, 95L, 90L, 60L), out.map { it.publishedAtMillis })
    }

    @Test
    fun capZeroReturnsAllSortedByRecency() {
        val items = listOf(item("A", 1), item("B", 3), item("A", 2))
        val out = NewsMerge.capPerSource(items, 0)
        assertEquals(listOf(3L, 2L, 1L), out.map { it.publishedAtMillis })
    }

    @Test
    fun blankSourceItemsAreNeverCapped() {
        val items = listOf(item("", 5), item("", 4), item("", 3), item("PAP", 6), item("PAP", 2))
        val out = NewsMerge.capPerSource(items, 1)
        assertEquals(listOf(6L, 5L, 4L, 3L), out.map { it.publishedAtMillis })
    }

    @Test
    fun sourceMatchIsCaseInsensitive() {
        val items = listOf(item("PAP", 3), item("pap", 2), item("Pap", 1))
        val out = NewsMerge.capPerSource(items, 1)
        assertEquals(listOf(3L), out.map { it.publishedAtMillis })
    }
}
