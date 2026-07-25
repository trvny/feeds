package com.kanarek.data

import org.junit.Assert.assertEquals
import org.junit.Test

class AppThemeModeTest {
    @Test
    fun `missing and invalid values follow the system`() {
        assertEquals(AppThemeMode.SYSTEM, AppThemeMode.fromStored(null))
        assertEquals(AppThemeMode.SYSTEM, AppThemeMode.fromStored("unexpected"))
    }

    @Test
    fun `stored modes round trip`() {
        AppThemeMode.entries.forEach { mode ->
            assertEquals(mode, AppThemeMode.fromStored(mode.name))
        }
    }
}
