package com.feedy.data

import java.net.URI

/**
 * Minimal OPML 2.0 reader/writer for feed lists — pure Kotlin, no Android deps (mirrors FeedParser).
 *
 * Import pulls every `xmlUrl` attribute (the standard place a feed URL lives in an OPML outline),
 * order-preserving and de-duplicated; nested folders are flattened. Export wraps the current feed
 * list in a flat OPML body. Tolerant of slightly malformed files — it never throws on bad input,
 * it just returns whatever URLs it could find.
 */
object Opml {

    private val XML_URL = Regex(
        """xmlUrl\s*=\s*"([^"]*)"|xmlUrl\s*=\s*'([^']*)'""",
        RegexOption.IGNORE_CASE,
    )

    /** Extract feed URLs from OPML text. */
    fun parse(xml: String): List<String> =
        XML_URL.findAll(xml)
            .map { it.groupValues[1].ifEmpty { it.groupValues[2] } }
            .map { unescape(it).trim() }
            .filter { it.isNotEmpty() }
            .distinct()
            .toList()

    /** Serialize feed URLs to an OPML 2.0 document. */
    fun build(feeds: List<String>, title: String = "feedy feeds"): String = buildString {
        append("""<?xml version="1.0" encoding="UTF-8"?>""").append('\n')
        append("""<opml version="2.0">""").append('\n')
        append("  <head><title>").append(escape(title)).append("</title></head>\n")
        append("  <body>\n")
        feeds.map { it.trim() }.filter { it.isNotEmpty() }.distinct().forEach { url ->
            val label = escape(labelOf(url))
            append("""    <outline type="rss" text="""").append(label)
                .append("""" title="""").append(label)
                .append("""" xmlUrl="""").append(escape(url)).append("\"/>\n")
        }
        append("  </body>\n")
        append("</opml>\n")
    }

    /** A friendly outline label: the feed's host without `www.`, falling back to the URL. */
    private fun labelOf(url: String): String =
        runCatching { URI(url).host?.removePrefix("www.") }.getOrNull()
            ?.takeIf { it.isNotBlank() } ?: url

    private fun escape(s: String): String = s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")

    private fun unescape(s: String): String = s
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&apos;", "'")
        .replace("&amp;", "&")
}
