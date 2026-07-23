package com.kanarek.data

import android.content.Context
import java.io.File
import java.security.MessageDigest

/**
 * Small on-disk cache of successful backend responses, used for conditional GET.
 *
 * One file per request URL, named by its SHA-1. The file is `etag\nbody`: an ETag is a
 * single quoted token with no newline, so splitting on the first `\n` is unambiguous.
 * Entries unused for 14 days are removed and the directory is kept below 8 MiB.
 *
 * Lives under `cacheDir`, so the OS may also evict it under storage pressure. A miss just
 * means the next fetch is a normal full GET instead of a conditional one.
 */
class FeedCache internal constructor(
    private val dir: File,
    private val nowMillis: () -> Long = { System.currentTimeMillis() },
    private val maxBytes: Long = DEFAULT_MAX_BYTES,
    private val maxAgeMillis: Long = DEFAULT_MAX_AGE_MILLIS,
) {
    constructor(context: Context) : this(File(context.cacheDir, "feed-http"))

    init {
        runCatching {
            dir.mkdirs()
            trim()
        }
    }

    data class Entry(
        val etag: String,
        val body: String,
    )

    fun keyFor(url: String): String =
        MessageDigest
            .getInstance("SHA-1")
            .digest(url.toByteArray())
            .joinToString("") { "%02x".format(it) }

    fun read(key: String): Entry? {
        val file = File(dir, key)
        if (!file.exists()) return null
        val now = nowMillis()
        if (isStale(file, now)) {
            file.delete()
            return null
        }
        val entry =
            runCatching {
                val text = file.readText()
                val newline = text.indexOf('\n')
                if (newline <= 0) null else Entry(text.substring(0, newline), text.substring(newline + 1))
            }.getOrNull()
        if (entry == null) {
            file.delete()
            return null
        }
        file.setLastModified(now)
        return entry
    }

    fun write(
        key: String,
        etag: String,
        body: String,
    ) {
        runCatching {
            dir.mkdirs()
            File(dir, key).apply {
                writeText(etag + "\n" + body)
                setLastModified(nowMillis())
            }
            trim()
        }
    }

    private fun trim() {
        val now = nowMillis()
        val files = dir.listFiles()?.filter(File::isFile).orEmpty()
        files.filter { isStale(it, now) }.forEach(File::delete)

        val remaining = dir.listFiles()?.filter(File::isFile).orEmpty()
        var totalBytes = remaining.sumOf(File::length)
        val targetBytes = maxBytes.coerceAtLeast(0L)
        if (totalBytes <= targetBytes) return

        remaining.sortedBy(File::lastModified).forEach { file ->
            if (totalBytes <= targetBytes) return
            val length = file.length()
            if (file.delete()) totalBytes -= length
        }
    }

    private fun isStale(
        file: File,
        now: Long,
    ): Boolean {
        val cutoff = (now - maxAgeMillis.coerceAtLeast(0L)).coerceAtLeast(0L)
        return file.lastModified() < cutoff
    }

    companion object {
        private const val DEFAULT_MAX_BYTES = 8L * 1024L * 1024L
        private const val DEFAULT_MAX_AGE_MILLIS = 14L * 24L * 60L * 60L * 1000L
    }
}
