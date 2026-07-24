package com.kanarek.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class StorageFilesTest {
    @Test
    fun usageSeparatesFeedAndImageCaches() {
        val root = Files.createTempDirectory("storage-files-test").toFile()
        try {
            val feeds = root.resolve("feeds").apply { mkdirs() }
            val images = root.resolve("images/nested").apply { mkdirs() }
            feeds.resolve("one").writeBytes(ByteArray(3))
            images.resolve("two").writeBytes(ByteArray(5))
            images.resolve("three").writeBytes(ByteArray(7))

            assertEquals(
                StorageUsage(feedCacheBytes = 3L, imageCacheBytes = 12L),
                StorageFiles.usage(
                    feedCacheRoots = listOf(feeds),
                    imageCacheRoots = listOf(root.resolve("images")),
                ),
            )
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun clearDirectoryKeepsRootAndDeletesNestedContents() {
        val root = Files.createTempDirectory("storage-files-test").toFile()
        try {
            root.resolve("nested").apply { mkdirs() }.resolve("item").writeText("cached")

            StorageFiles.clearDirectory(root)

            assertTrue(root.exists())
            assertFalse(root.resolve("nested").exists())
            assertEquals(0L, StorageFiles.sizeOf(root))
        } finally {
            root.deleteRecursively()
        }
    }

    @Test
    fun missingRootsHaveZeroSize() {
        val root = Files.createTempDirectory("storage-files-test").toFile()
        try {
            assertEquals(0L, StorageFiles.sizeOf(root.resolve("missing")))
        } finally {
            root.deleteRecursively()
        }
    }
}
