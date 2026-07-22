package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Test

class M3uGroupTagsTest {
    @Test
    fun parsesExtAlbAsGroupFallback() {
        val station =
            M3uCodec.parse(
                """
                #EXTINF:-1,Radio One
                #EXTALB:BBC
                https://example.com/live.m3u8
                """.trimIndent(),
            ).single()

        assertEquals("BBC", station.groupTitle)
    }

    @Test
    fun explicitGroupTitleBeatsStandaloneTag() {
        val station =
            M3uCodec.parse(
                """
                #EXTINF:-1 group-title="News",Radio One
                #EXTGRP:Fallback
                https://example.com/live.mp3
                """.trimIndent(),
            ).single()

        assertEquals("News", station.groupTitle)
    }
}
