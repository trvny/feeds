package com.kanarek.widget

import com.kanarek.data.NewsItem
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

internal enum class WidgetRefreshScheduleAction { ENSURE, CANCEL }

internal object WidgetRefreshPolicy {
    fun scheduleAction(activeWidgetIds: IntArray): WidgetRefreshScheduleAction =
        if (activeWidgetIds.isEmpty()) {
            WidgetRefreshScheduleAction.CANCEL
        } else {
            WidgetRefreshScheduleAction.ENSURE
        }

    fun selectTargets(
        requestedWidgetIds: IntArray?,
        activeWidgetIds: IntArray,
    ): IntArray {
        val active = activeWidgetIds.toSet()
        return (requestedWidgetIds ?: activeWidgetIds)
            .asSequence()
            .filter(active::contains)
            .distinct()
            .toList()
            .toIntArray()
    }
}

internal data class WidgetRefreshOutcome(
    val snapshot: NewsWidgetSnapshot?,
    val saveSnapshot: Boolean,
    val shouldRetry: Boolean,
)

internal fun widgetRefreshOutcome(
    previous: NewsWidgetSnapshot?,
    fetched: List<NewsItem>,
    fetchSucceeded: Boolean,
    nowMillis: Long,
): WidgetRefreshOutcome =
    if (fetched.isNotEmpty()) {
        WidgetRefreshOutcome(
            snapshot = NewsWidgetSnapshot(items = fetched, lastUpdatedMillis = nowMillis),
            saveSnapshot = true,
            shouldRetry = false,
        )
    } else {
        WidgetRefreshOutcome(
            snapshot = previous,
            saveSnapshot = false,
            shouldRetry = !fetchSucceeded,
        )
    }

internal class WidgetRefreshSingleFlight {
    private val mutex = Mutex()

    suspend fun <T> run(block: suspend () -> T): T = mutex.withLock { block() }
}
