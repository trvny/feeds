package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ArticleReaderTest {
    @Test
    fun cleanReaderRequiresExplicitPublicBackend() {
        assertNull(configuredReaderBackend(""))
        assertNull(configuredReaderBackend("   "))
        assertNull(configuredReaderBackend("not a url"))
        assertNull(configuredReaderBackend("file:///tmp/worker"))
        assertEquals(
            "https://worker.example",
            configuredReaderBackend("  https://worker.example/  "),
        )
    }
}
