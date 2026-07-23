package com.kanarek.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FeedCacheTest {
    @Test
    fun staleEntriesAreDeletedOnRead() {
        val dir = Files.createTempDirectory("feed-cache-test").toFile()
        var now = 1_700_000_000_000L
        try {
            val cache =
                FeedCache(
                    dir = dir,
                    nowMillis = { now },
                    maxBytes = 1_024L,
                    maxAgeMillis = 1_000L,
                )
            cache.write("entry", "etag", "body")
            now += 1_001L

            assertNull(cache.read("entry"))
            assertFalse(dir.resolve("entry").exists())
        } finally {
            dir.deleteRecursively()
        }
    }

    @Test
    fun writesEvictLeastRecentlyUsedEntriesAboveLimit() {
        val dir = Files.createTempDirectory("feed-cache-test").toFile()
        var now = 1_700_000_000_000L
        try {
            val cache =
                FeedCache(
                    dir = dir,
                    nowMillis = { now },
                    maxBytes = 19L,
                    maxAgeMillis = 10_000L,
                )
            cache.write("old", "e", "12345678")
            now += 100L
            cache.write("recent", "e", "12345678")

            assertFalse(dir.resolve("old").exists())
            assertTrue(dir.resolve("recent").exists())
            assertEquals(FeedCache.Entry("e", "12345678"), cache.read("recent"))
        } finally {
            dir.deleteRecursively()
        }
    }
}
