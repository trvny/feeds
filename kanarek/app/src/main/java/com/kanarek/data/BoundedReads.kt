package com.kanarek.data

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream

/** Read at most [maxBytes], failing before an untrusted response can grow without bound in memory. */
internal fun InputStream.readBytesCapped(maxBytes: Int): ByteArray {
    require(maxBytes > 0) { "maxBytes must be positive" }
    val output = ByteArrayOutputStream(minOf(maxBytes, DEFAULT_BUFFER_SIZE))
    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
    var total = 0
    while (true) {
        val count = read(buffer)
        if (count < 0) break
        total += count
        if (total > maxBytes) throw IOException("response exceeds $maxBytes bytes")
        output.write(buffer, 0, count)
    }
    return output.toByteArray()
}

/** UTF-8 counterpart to [readBytesCapped]. */
internal fun InputStream.readTextCapped(maxBytes: Int): String = readBytesCapped(maxBytes).toString(Charsets.UTF_8)
