package com.kanarek.data

import java.net.URI

/** Validation shared by the reader and widget paths for links supplied by untrusted feeds. */
object WebLinks {
    fun isHttpOrHttps(raw: String): Boolean {
        val scheme = runCatching { URI(raw.trim()).scheme?.lowercase() }.getOrNull()
        return scheme == "http" || scheme == "https"
    }
}
