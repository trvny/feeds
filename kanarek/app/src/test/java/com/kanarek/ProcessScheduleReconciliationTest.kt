package com.kanarek

import android.app.Application
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ProcessScheduleReconciliationTest {
    @Test
    fun `application owns process-start reconciliation`() {
        val application = RuntimeEnvironment.getApplication<Application>()

        assertTrue(application is KanarekApplication)
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
            syncReader = readerIntervals::add,
            syncNotifications = notificationStates::add,
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
            syncReader = readerIntervals::add,
            syncNotifications = notificationStates::add,
        )

        assertEquals(listOf(0), readerIntervals)
        assertEquals(listOf(false), notificationStates)
    }
}
