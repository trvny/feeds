package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HeadlinesTest {
    private val now = 1_700_000_000_000L

    private fun item(
        title: String,
        source: String,
        ageHours: Double = 0.0,
        image: String? = null,
    ) = NewsItem(
        title = title,
        link = "https://$source.example/${title.hashCode()}",
        summary = "",
        imageUrl = image,
        source = source,
        publishedAtMillis = now - (ageHours * 3_600_000.0).toLong(),
    )

    @Test fun empty_input_yields_empty() {
        assertEquals(emptyList<NewsItem>(), Headlines.rank(emptyList(), nowMillis = now))
    }

    @Test fun newer_outranks_older_when_otherwise_equal() {
        val older = item("Alpha beta gamma delta", "A", ageHours = 48.0)
        val newer = item("Zeta theta kappa lambda", "B", ageHours = 1.0)
        val ranked = Headlines.rank(listOf(older, newer), topSources = emptySet(), nowMillis = now)
        assertEquals(newer.link, ranked.first().item.link)
    }

    @Test fun image_outranks_no_image_when_same_age() {
        val plain = item("Alpha beta gamma delta", "A", ageHours = 5.0)
        val withPic = item("Zeta theta kappa lambda", "B", ageHours = 5.0, image = "https://x/y.jpg")
        val ranked = Headlines.rank(listOf(plain, withPic), topSources = emptySet(), nowMillis = now)
        assertEquals(withPic.link, ranked.first().item.link)
    }

    @Test fun top_source_outranks_regular_when_same_age() {
        val regular = item("Alpha beta gamma delta", "Randomblog", ageHours = 5.0)
        val top = item("Zeta theta kappa lambda", "Reuters", ageHours = 5.0)
        val ranked = Headlines.rank(listOf(regular, top), topSources = setOf("reuters"), nowMillis = now)
        assertEquals(top.link, ranked.first().item.link)
    }

    @Test fun corroborated_story_outranks_fresher_singleton() {
        // Same story from three sources, a bit old; one unrelated very fresh singleton.
        val t = "Government announces major budget reform package today"
        val a = item(t, "SourceA", ageHours = 12.0)
        val b = item("Major budget reform package announced by government", "SourceB", ageHours = 12.0)
        val c = item("Budget reform package: government announces major changes", "SourceC", ageHours = 12.0)
        val fresh = item("Local bakery wins regional pastry contest", "SourceD", ageHours = 0.5)
        val ranked = Headlines.rank(listOf(fresh, a, b, c), topSources = emptySet(), nowMillis = now)
        // The top result should be one of the three corroborated items, not the fresh singleton.
        assertTrue(ranked.first().item.source in setOf("SourceA", "SourceB", "SourceC"))
    }

    @Test fun headlines_respects_limit() {
        val items = (1..10).map { item("Story number $it about something", "S$it", ageHours = it.toDouble()) }
        assertEquals(3, Headlines.headlines(items, topSources = emptySet(), limit = 3, nowMillis = now).size)
    }

    @Test fun unrelated_titles_do_not_corroborate() {
        val x = item("Weather forecast sunny tomorrow", "A", ageHours = 10.0)
        val y = item("Stock market closes higher today", "B", ageHours = 10.0)
        val z = item("Football team signs new striker", "C", ageHours = 10.0)
        // None share enough significant tokens; ranking falls back to recency ties — all valid, no crash.
        val ranked = Headlines.rank(listOf(x, y, z), topSources = emptySet(), nowMillis = now)
        assertEquals(3, ranked.size)
    }
}
