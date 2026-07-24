package com.kanarek.widget

import com.kanarek.data.NewsItem
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class WidgetRefreshCoordinatorTest {
    @Test
    fun scheduleFollowsWidgetLifecycle() {
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(intArrayOf(1)),
        )
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(intArrayOf(1, 2)),
        )
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(intArrayOf(2)),
        )
        assertEquals(
            WidgetRefreshScheduleAction.CANCEL,
            WidgetRefreshPolicy.scheduleAction(intArrayOf()),
        )
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(intArrayOf(3)),
        )
    }

    @Test
    fun restartReconciliationStillEnsuresTheUniqueSchedule() {
        val active = intArrayOf(7)

        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(active),
        )
        assertEquals(
            WidgetRefreshScheduleAction.ENSURE,
            WidgetRefreshPolicy.scheduleAction(active),
        )
    }

    @Test
    fun manualTargetsAreActiveAndDeduplicated() {
        assertEquals(
            listOf(2),
            WidgetRefreshPolicy
                .selectTargets(
                    requestedWidgetIds = intArrayOf(2, 2, 3),
                    activeWidgetIds = intArrayOf(1, 2),
                ).toList(),
        )
        assertEquals(
            listOf(1, 2),
            WidgetRefreshPolicy
                .selectTargets(
                    requestedWidgetIds = null,
                    activeWidgetIds = intArrayOf(1, 2),
                ).toList(),
        )
    }

    @Test
    fun failedRefreshPreservesLastGoodSnapshot() {
        val previous = NewsWidgetSnapshot(items = listOf(item("old")), lastUpdatedMillis = 10L)

        val outcome =
            widgetRefreshOutcome(
                previous = previous,
                fetched = emptyList(),
                fetchSucceeded = false,
                nowMillis = 20L,
            )

        assertTrue(outcome.shouldRetry)
        assertFalse(outcome.saveSnapshot)
        assertSame(previous, outcome.snapshot)
    }

    @Test
    fun emptySuccessfulFeedDoesNotRetryOrReplaceSnapshot() {
        val previous = NewsWidgetSnapshot(items = listOf(item("old")), lastUpdatedMillis = 10L)

        val outcome =
            widgetRefreshOutcome(
                previous = previous,
                fetched = emptyList(),
                fetchSucceeded = true,
                nowMillis = 20L,
            )

        assertFalse(outcome.shouldRetry)
        assertFalse(outcome.saveSnapshot)
        assertSame(previous, outcome.snapshot)
    }

    @Test
    fun successfulRefreshReplacesSnapshotTimestamp() {
        val fetched = listOf(item("new"))

        val outcome =
            widgetRefreshOutcome(
                previous = null,
                fetched = fetched,
                fetchSucceeded = true,
                nowMillis = 20L,
            )

        assertFalse(outcome.shouldRetry)
        assertTrue(outcome.saveSnapshot)
        assertEquals(NewsWidgetSnapshot(fetched, 20L), outcome.snapshot)
    }

    @Test
    fun refreshesNeverRunInParallel() =
        runBlocking {
            val gate = WidgetRefreshSingleFlight()
            val firstEntered = CompletableDeferred<Unit>()
            val releaseFirst = CompletableDeferred<Unit>()
            val secondEntered = CompletableDeferred<Unit>()
            val active = AtomicInteger(0)
            val maximumActive = AtomicInteger(0)

            suspend fun recordRefresh(
                entered: CompletableDeferred<Unit>,
                release: CompletableDeferred<Unit>? = null,
            ) {
                val current = active.incrementAndGet()
                maximumActive.updateAndGet { previous -> maxOf(previous, current) }
                entered.complete(Unit)
                release?.await()
                active.decrementAndGet()
            }

            val first =
                async(Dispatchers.Default) {
                    gate.run { recordRefresh(firstEntered, releaseFirst) }
                }
            firstEntered.await()
            val second =
                async(Dispatchers.Default) {
                    gate.run { recordRefresh(secondEntered) }
                }
            yield()

            assertFalse(secondEntered.isCompleted)
            releaseFirst.complete(Unit)
            first.await()
            second.await()
            assertEquals(1, maximumActive.get())
        }

    private fun item(name: String): NewsItem =
        NewsItem(
            title = name,
            link = "https://example.com/$name",
            summary = "",
            imageUrl = null,
            source = "Example",
            publishedAtMillis = null,
        )
}
