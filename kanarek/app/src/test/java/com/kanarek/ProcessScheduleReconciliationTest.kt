package com.kanarek

import androidx.work.WorkManagerInitializer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProcessScheduleReconciliationTest {
    @Test
    fun `process reconciliation starts after WorkManager`() {
        val dependencies = KanarekProcessInitializer().dependencies()

        assertTrue(WorkManagerInitializer::class.java in dependencies)
    }

    @Test
    fun `persisted reader and notification schedules are both restored`() {
        val readerIntervals = mutableListOf<Int>()
        val notificationStates = mutableListOf<Boolean>()

        reconcilePersistedSchedules(
            state =
                ProcessScheduleState(
                    readerRefreshMinutes = 60,
                    notificationsEnabled = true,
                ),
            syncReader = { minutes -> readerIntervals += minutes },
            syncNotifications = { enabled -> notificationStates += enabled },
        )

        assertEquals(listOf(60), readerIntervals)
        assertEquals(listOf(true), notificationStates)
    }

    @Test
    fun `disabled persisted schedules are actively cancelled`() {
        val readerIntervals = mutableListOf<Int>()
        val notificationStates = mutableListOf<Boolean>()

        reconcilePersistedSchedules(
            state =
                ProcessScheduleState(
                    readerRefreshMinutes = 0,
                    notificationsEnabled = false,
                ),
            syncReader = { minutes -> readerIntervals += minutes },
            syncNotifications = { enabled -> notificationStates += enabled },
        )

        assertEquals(listOf(0), readerIntervals)
        assertEquals(listOf(false), notificationStates)
    }
}
