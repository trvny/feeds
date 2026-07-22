package com.kanarek.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WebLinksTest {
    @Test
    fun acceptsHttpAndHttps() {
        assertTrue(WebLinks.isHttpOrHttps("https://example.com/article"))
        assertTrue(WebLinks.isHttpOrHttps("HTTP://example.com/article"))
        assertTrue(WebLinks.isHttpOrHttps("  https://example.com/trimmed  "))
    }

    @Test
    fun rejectsNonWebAndMalformedLinks() {
        assertFalse(WebLinks.isHttpOrHttps("intent://example/#Intent;scheme=https;end"))
        assertFalse(WebLinks.isHttpOrHttps("javascript:alert(1)"))
        assertFalse(WebLinks.isHttpOrHttps("example.com/no-scheme"))
        assertFalse(WebLinks.isHttpOrHttps(""))
    }
}
