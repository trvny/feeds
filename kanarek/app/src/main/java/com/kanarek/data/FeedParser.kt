package com.kanarek.data

import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeFormatterBuilder
import java.time.format.SignStyle
import java.time.temporal.ChronoField
import java.util.Locale

/**
 * Minimal RSS 2.0 / Atom parser. Regex-based, no DOM — good enough for
 * well-formed feeds and dependency-free. One source can't crash another;
 * callers wrap each feed fetch in its own try/catch.
 */
object FeedParser {
    fun parse(xml: String): List<NewsItem> {
        val source = stripTags(decode(textOf(first(xml, "title")) ?: "")).trim()
        val isAtom =
            Regex("<feed[\\s>]", RegexOption.IGNORE_CASE).containsMatchIn(xml) &&
                Regex("<entry[\\s>]", RegexOption.IGNORE_CASE).containsMatchIn(xml)
        val blocks = blocksOf(xml, if (isAtom) "entry" else "item")

        return blocks.mapNotNull { block ->
            val title = textOf(first(block, "title"))?.let { stripTags(decode(it)).trim() }
            val link = if (isAtom) atomLink(block) else textOf(first(block, "link"))?.let { decode(it).trim() }
            if (title.isNullOrBlank() || link.isNullOrBlank()) return@mapNotNull null

            val rawSummary =
                textOf(first(block, if (isAtom) "summary" else "description"))
                    ?: textOf(first(block, "content"))
            val summary = stripTags(decode(stripTags(rawSummary ?: ""))).trim().take(280)

            val dateStr =
                textOf(first(block, if (isAtom) "updated" else "pubDate"))
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

    private fun blocksOf(
        xml: String,
        tag: String,
    ): List<String> = Regex("<$tag[\\s>][\\s\\S]*?</$tag>", RegexOption.IGNORE_CASE).findAll(xml).map { it.value }.toList()

    private fun first(
        xml: String,
        tag: String,
    ): String? = Regex("<$tag(?:\\s[^>]*)?>([\\s\\S]*?)</$tag>", RegexOption.IGNORE_CASE).find(xml)?.groupValues?.get(1)

    private fun textOf(s: String?): String? {
        if (s == null) return null
        val cdata = Regex("<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>").find(s)
        return (cdata?.groupValues?.get(1) ?: s).trim()
    }

    private fun atomLink(block: String): String? {
        val patterns =
            listOf(
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
        val patterns =
            listOf(
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

    private fun stripTags(s: String): String = s.replace(Regex("<[^>]+>"), " ").replace(Regex("\\s+"), " ").trim()

    private fun decode(s: String): String =
        s
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
            .replace("&#39;", "'")
            .replace("&#039;", "'")
            .replace("&apos;", "'")
            .replace("&#x2F;", "/")
            .replace("&nbsp;", " ")
            .replace(Regex("&#(\\d+);")) {
                runCatching {
                    it.groupValues[1]
                        .toInt()
                        .toChar()
                        .toString()
                }.getOrDefault("")
            }.replace(Regex("&#x([0-9a-fA-F]+);")) {
                runCatching {
                    it.groupValues[1]
                        .toInt(16)
                        .toChar()
                        .toString()
                }.getOrDefault("")
            }.replace("&amp;", "&")

    private fun hostOf(link: String): String =
        runCatching {
            java.net
                .URI(link)
                .host
                ?.removePrefix("www.") ?: ""
        }.getOrDefault("")

    /** Thread-safe java.time parsing; FeedParser is called concurrently for several sources. */
    private fun parseDate(s: String?): Long? {
        val value = textOf(s)?.trim()?.takeIf { it.isNotEmpty() } ?: return null
        return runCatching { Instant.parse(value).toEpochMilli() }.getOrNull()
            ?: runCatching { OffsetDateTime.parse(value, DateTimeFormatter.ISO_OFFSET_DATE_TIME).toInstant().toEpochMilli() }.getOrNull()
            ?: runCatching { OffsetDateTime.parse(value, RFC_OFFSET).toInstant().toEpochMilli() }.getOrNull()
            ?: runCatching { ZonedDateTime.parse(value, RFC_ZONE).toInstant().toEpochMilli() }.getOrNull()
            ?: runCatching { OffsetDateTime.parse(value, COMPACT_OFFSET).toInstant().toEpochMilli() }.getOrNull()
            ?: runCatching { LocalDate.parse(value, DateTimeFormatter.ISO_LOCAL_DATE).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli() }
                .getOrNull()
    }

    /**
     * Human-readable age for the reader UI without Android dependencies. [locale] is explicit so
     * JVM tests stay deterministic; callers normally use the current default locale.
     */
    fun relativeTime(
        millis: Long?,
        now: Long = System.currentTimeMillis(),
        locale: Locale = Locale.getDefault(),
    ): String {
        if (millis == null) return ""
        val seconds = ((now - millis).coerceAtLeast(0L)) / 1000L
        val language = locale.language.lowercase(Locale.ROOT)
        return when {
            seconds < 60L -> if (language == "pl") "przed chwilą" else "just now"
            seconds < 3_600L -> formatAge(seconds / 60L, AgeUnit.MINUTE, language)
            seconds < 86_400L -> formatAge(seconds / 3_600L, AgeUnit.HOUR, language)
            else -> formatAge(seconds / 86_400L, AgeUnit.DAY, language)
        }
    }

    private enum class AgeUnit { MINUTE, HOUR, DAY }

    private fun formatAge(
        count: Long,
        unit: AgeUnit,
        language: String,
    ): String =
        if (language == "pl") {
            val word =
                when (unit) {
                    AgeUnit.MINUTE -> polishForm(count, "minutę", "minuty", "minut")
                    AgeUnit.HOUR -> polishForm(count, "godzinę", "godziny", "godzin")
                    AgeUnit.DAY -> polishForm(count, "dzień", "dni", "dni")
                }
            "$count $word temu"
        } else {
            val word =
                when (unit) {
                    AgeUnit.MINUTE -> if (count == 1L) "minute" else "minutes"
                    AgeUnit.HOUR -> if (count == 1L) "hour" else "hours"
                    AgeUnit.DAY -> if (count == 1L) "day" else "days"
                }
            "$count $word ago"
        }

    private fun polishForm(
        count: Long,
        one: String,
        few: String,
        many: String,
    ): String {
        if (count == 1L) return one
        val lastTwo = count % 100L
        val last = count % 10L
        return if (last in 2L..4L && lastTwo !in 12L..14L) few else many
    }

    private val RFC_OFFSET =
        DateTimeFormatterBuilder()
            .parseCaseInsensitive()
            .appendPattern("EEE, ")
            .appendValue(ChronoField.DAY_OF_MONTH, 1, 2, SignStyle.NOT_NEGATIVE)
            .appendPattern(" MMM yyyy HH:mm:ss Z")
            .toFormatter(Locale.US)

    private val RFC_ZONE =
        DateTimeFormatterBuilder()
            .parseCaseInsensitive()
            .appendPattern("EEE, ")
            .appendValue(ChronoField.DAY_OF_MONTH, 1, 2, SignStyle.NOT_NEGATIVE)
            .appendPattern(" MMM yyyy HH:mm:ss zzz")
            .toFormatter(Locale.US)

    private val COMPACT_OFFSET = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ssZ", Locale.US)
}
