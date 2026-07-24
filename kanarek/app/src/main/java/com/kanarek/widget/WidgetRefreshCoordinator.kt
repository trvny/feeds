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
    val successful: Boolean,
)

internal fun widgetRefreshOutcome(
    previous: NewsWidgetSnapshot?,
    fetched: List<NewsItem>,
    nowMillis: Long,
): WidgetRefreshOutcome =
    if (fetched.isNotEmpty()) {
        WidgetRefreshOutcome(
            snapshot = NewsWidgetSnapshot(items = fetched, lastUpdatedMillis = nowMillis),
            successful = true,
        )
    } else {
        WidgetRefreshOutcome(snapshot = previous, successful = false)
    }

internal class WidgetRefreshSingleFlight {
    private val mutex = Mutex()

    suspend fun <T> run(block: suspend () -> T): T = mutex.withLock { block() }
}
