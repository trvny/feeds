package com.fidy.data

import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/**
 * Minimal RSS 2.0 / Atom parser. Regex-based, no DOM — good enough for
 * well-formed feeds and dependency-free. One source can't crash another;
 * callers wrap each feed fetch in its own try/catch.
 */
object FeedParser {

    fun parse(xml: String): List<NewsItem> {
        val source = stripTags(decode(textOf(first(xml, "title")) ?: "")).trim()
        val isAtom = Regex("<feed[\\s>]", RegexOption.IGNORE_CASE).containsMatchIn(xml) &&
            Regex("<entry[\\s>]", RegexOption.IGNORE_CASE).containsMatchIn(xml)
        val blocks = blocksOf(xml, if (isAtom) "entry" else "item")

        return blocks.mapNotNull { block ->
            val title = textOf(first(block, "title"))?.let { stripTags(decode(it)).trim() }
            val link = if (isAtom) atomLink(block) else textOf(first(block, "link"))?.let { decode(it).trim() }
            if (title.isNullOrBlank() || link.isNullOrBlank()) return@mapNotNull null

            val rawSummary = textOf(first(block, if (isAtom) "summary" else "description"))
                ?: textOf(first(block, "content"))
            val summary = stripTags(decode(stripTags(rawSummary ?: ""))).trim().take(280)

            val dateStr = textOf(first(block, if (isAtom) "updated" else "pubDate"))
                ?: textOf(first(block, "published"))
                ?: textOf(first(block, "date"))

            NewsItem(
                title = title,
                link = link,
                summary = summary,
                imageUrl = imageOf(block),
                source = source.ifBlank { hostOf(link) },
                publishedAtMillis = parseDate(dateStr),
            )
        }
    }

    private fun blocksOf(xml: String, tag: String): List<String> =
        Regex("<$tag[\\s>][\\s\\S]*?</$tag>", RegexOption.IGNORE_CASE).findAll(xml).map { it.value }.toList()

    private fun first(xml: String, tag: String): String? =
        Regex("<$tag(?:\\s[^>]*)?>([\\s\\S]*?)</$tag>", RegexOption.IGNORE_CASE).find(xml)?.groupValues?.get(1)

    private fun textOf(s: String?): String? {
        if (s == null) return null
        val cdata = Regex("<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>").find(s)
        return (cdata?.groupValues?.get(1) ?: s).trim()
    }

    private fun atomLink(block: String): String? {
        val patterns = listOf(
            "<link[^>]*rel=[\"']alternate[\"'][^>]*href=[\"']([^\"']+)[\"']",
            "<link[^>]*href=[\"']([^\"']+)[\"'][^>]*rel=[\"']alternate[\"']",
            "<link[^>]*href=[\"']([^\"']+)[\"']",
        )
        for (p in patterns) {
            Regex(p, RegexOption.IGNORE_CASE).find(block)?.let { return decode(it.groupValues[1]).trim() }
        }
        return null
    }

    private fun imageOf(block: String): String? {
        val patterns = listOf(
            "<media:content[^>]*url=[\"']([^\"']+)[\"']",
            "<media:thumbnail[^>]*url=[\"']([^\"']+)[\"']",
            "<enclosure[^>]*url=[\"']([^\"']+\\.(?:jpg|jpeg|png|webp|gif)[^\"']*)[\"']",
            "<image>[\\s\\S]*?<url>([\\s\\S]*?)</url>",
            "<img[^>]*src=[\"']([^\"']+)[\"']",
        )
        for (p in patterns) {
            Regex(p, RegexOption.IGNORE_CASE).find(block)?.let { return decode(it.groupValues[1]).trim() }
        }
        return null
    }

    private fun stripTags(s: String): String =
        s.replace(Regex("<[^>]+>"), " ").replace(Regex("\\s+"), " ").trim()

    private fun decode(s: String): String = s
        .replace("&lt;", "<").replace("&gt;", ">")
        .replace("&quot;", "\"").replace("&#39;", "'").replace("&#039;", "'").replace("&apos;", "'")
        .replace("&#x2F;", "/").replace("&nbsp;", " ")
        .replace(Regex("&#(\\d+);")) { runCatching { it.groupValues[1].toInt().toChar().toString() }.getOrDefault("") }
        .replace(Regex("&#x([0-9a-fA-F]+);")) { runCatching { it.groupValues[1].toInt(16).toChar().toString() }.getOrDefault("") }
        .replace("&amp;", "&")

    private fun hostOf(link: String): String =
        runCatching { java.net.URI(link).host?.removePrefix("www.") ?: "" }.getOrDefault("")

    private val dateFormats: List<SimpleDateFormat> by lazy {
        listOf(
            "EEE, dd MMM yyyy HH:mm:ss Z",
            "EEE, dd MMM yyyy HH:mm:ss zzz",
            "yyyy-MM-dd'T'HH:mm:ssXXX",
            "yyyy-MM-dd'T'HH:mm:ss'Z'",
            "yyyy-MM-dd'T'HH:mm:ssZ",
            "yyyy-MM-dd",
        ).map { SimpleDateFormat(it, Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") } }
    }

    private fun parseDate(s: String?): Long? {
        val v = textOf(s)?.trim() ?: return null
        if (v.isBlank()) return null
        for (fmt in dateFormats) {
            runCatching { return fmt.parse(v)?.time }
        }
        return null
    }

    // Exposed for the host-app preview formatting.
    fun relativeTime(millis: Long?, now: Long = System.currentTimeMillis()): String {
        if (millis == null) return ""
        val diff = (now - millis) / 1000
        return when {
            diff < 60 -> "just now"
            diff < 3600 -> "${diff / 60}m ago"
            diff < 86400 -> "${diff / 3600}h ago"
            else -> "${diff / 86400}d ago"
        }
    }

}
