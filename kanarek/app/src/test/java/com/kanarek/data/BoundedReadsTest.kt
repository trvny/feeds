package com.kanarek.data

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.IOException

class BoundedReadsTest {
    @Test
    fun readsPayloadAtLimit() {
        val bytes = byteArrayOf(1, 2, 3, 4)
        assertArrayEquals(bytes, ByteArrayInputStream(bytes).readBytesCapped(4))
    }

    @Test(expected = IOException::class)
    fun rejectsPayloadOverLimit() {
        ByteArrayInputStream(byteArrayOf(1, 2, 3, 4, 5)).readBytesCapped(4)
    }

    @Test
    fun decodesUtf8Text() {
        val text = "zażółć"
        assertEquals(text, ByteArrayInputStream(text.toByteArray()).readTextCapped(32))
    }
}
