package com.kanarek.data

import android.content.Context
import java.io.File
import java.security.MessageDigest

/**
 * Tiny on-disk cache of the last successful backend response, used for conditional GET.
 *
 * One file per request URL, named by its SHA-1. The file is `etag\nbody`: an ETag is a
 * single quoted token with no newline, so splitting on the first `\n` is unambiguous.
 *
 * Lives under `cacheDir`, so the OS may evict it under storage pressure — that's fine:
 * a miss just means the next fetch is a normal full GET instead of a conditional one.
 */
class FeedCache(
    context: Context,
) {
    private val dir: File = File(context.cacheDir, "feed-http").apply { mkdirs() }

    data class Entry(
        val etag: String,
        val body: String,
    )

    fun keyFor(url: String): String =
        MessageDigest
            .getInstance("SHA-1")
            .digest(url.toByteArray())
            .joinToString("") { "%02x".format(it) }

    fun read(key: String): Entry? =
        runCatching {
            val f = File(dir, key)
            if (!f.exists()) return null
            val text = f.readText()
            val nl = text.indexOf('\n')
            if (nl <= 0) null else Entry(text.substring(0, nl), text.substring(nl + 1))
        }.getOrNull()

    fun write(
        key: String,
        etag: String,
        body: String,
    ) {
        runCatching { File(dir, key).writeText(etag + "\n" + body) }
    }
}
