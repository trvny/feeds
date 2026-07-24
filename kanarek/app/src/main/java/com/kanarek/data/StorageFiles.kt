package com.kanarek.data

import java.io.File

internal data class StorageUsage(
    val feedCacheBytes: Long = 0L,
    val imageCacheBytes: Long = 0L,
)

/** File-only storage accounting kept Android-free for JVM tests. */
internal object StorageFiles {
    fun usage(
        feedCacheRoots: Iterable<File>,
        imageCacheRoots: Iterable<File>,
    ): StorageUsage =
        StorageUsage(
            feedCacheBytes = feedCacheRoots.sumOf(::sizeOf),
            imageCacheBytes = imageCacheRoots.sumOf(::sizeOf),
        )

    fun sizeOf(file: File): Long =
        when {
            !file.exists() -> 0L
            file.isFile -> file.length().coerceAtLeast(0L)
            else -> file.listFiles()?.sumOf(::sizeOf) ?: 0L
        }

    fun clearDirectory(directory: File) {
        directory.listFiles()?.forEach { it.deleteRecursively() }
    }
}
