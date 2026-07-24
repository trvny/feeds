package com.kanarek.data

internal enum class ReaderRefreshScheduleAction { SCHEDULE, CANCEL }

internal object ReaderBackgroundRefresh {
    const val OFF = 0
    const val MINUTES_30 = 30
    const val HOUR_1 = 60
    const val HOURS_3 = 180
    const val HOURS_6 = 360

    val options: List<Int> = listOf(OFF, MINUTES_30, HOUR_1, HOURS_3, HOURS_6)

    fun normalize(minutes: Int): Int = minutes.takeIf(options::contains) ?: OFF

    fun scheduleAction(minutes: Int): ReaderRefreshScheduleAction =
        if (normalize(minutes) == OFF) {
            ReaderRefreshScheduleAction.CANCEL
        } else {
            ReaderRefreshScheduleAction.SCHEDULE
        }
}
