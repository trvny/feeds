package com.feedy.widget

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import java.io.File
import java.security.MessageDigest

/**
 * Bounded two-tier bitmap cache for widget images: a process-wide in-memory LRU
 * (byte-sized) over a size-capped on-disk JPEG cache. Without this the widget
 * re-downloads every article image on every refresh/rebuild — the main data and
 * battery cost in the widget path. Pure framework APIs, no new dependencies.
 */
internal object WidgetImageCache {

    private const val MEM_BYTES = 6 * 1024 * 1024          // ~6 MB resident
    private const val DISK_BYTES = 12L * 1024 * 1024       // ~12 MB on disk
    private const val DIR = "widget_images"
    private const val JPEG_QUALITY = 85

    private val mem = object : LruCache<String, Bitmap>(MEM_BYTES) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.allocationByteCount
    }

    fun get(context: Context, key: String): Bitmap? {
        mem.get(key)?.let { return it }
        val file = fileFor(context, key)
        if (!file.exists()) return null
        val bitmap = runCatching { BitmapFactory.decodeFile(file.path) }.getOrNull() ?: return null
        file.setLastModified(System.currentTimeMillis()) // touch for LRU-on-disk
        mem.put(key, bitmap)
        return bitmap
    }

    fun put(context: Context, key: String, bitmap: Bitmap) {
        mem.put(key, bitmap)
        runCatching {
            val file = fileFor(context, key)
            file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, it) }
            trim(file.parentFile)
        }
    }

    private fun fileFor(context: Context, key: String): File =
        File(File(context.cacheDir, DIR).apply { mkdirs() }, hash(key))

    /** Evict oldest files until the directory is under the disk budget. */
    private fun trim(dir: File?) {
        val files = dir?.listFiles()?.sortedBy { it.lastModified() } ?: return
        var total = files.sumOf { it.length() }
        for (file in files) {
            if (total <= DISK_BYTES) break
            total -= file.length()
            file.delete()
        }
    }

    private fun hash(s: String): String =
        MessageDigest.getInstance("SHA-1").digest(s.toByteArray())
            .joinToString("") { "%02x".format(it.toInt() and 0xFF) }
}
