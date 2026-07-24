package com.kanarek.widget

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.kanarek.R
import com.kanarek.data.FeedCache
import com.kanarek.data.NewsFetchResult
import com.kanarek.data.NewsRepository
import com.kanarek.data.SettingsStore
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Fetches widget feeds through one periodic schedule and serialized manual work. */
class WidgetRefreshWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result =
        singleFlight.run {
            val activeIds = activeWidgetIds(applicationContext)
            val targets =
                WidgetRefreshPolicy.selectTargets(
                    requestedWidgetIds = inputData.getIntArray(KEY_WIDGET_IDS),
                    activeWidgetIds = activeIds,
                )
            if (targets.isEmpty()) {
                if (activeIds.isEmpty()) cancel(applicationContext)
                return@run Result.success()
            }

            val shouldRetry =
                withContext(Dispatchers.IO) {
                    refreshWidgets(targets)
                }
            val remainingTargets =
                WidgetRefreshPolicy.selectTargets(
                    requestedWidgetIds = targets,
                    activeWidgetIds = activeWidgetIds(applicationContext),
                )
            if (remainingTargets.isNotEmpty()) {
                AppWidgetManager.getInstance(applicationContext)
                    .notifyAppWidgetViewDataChanged(remainingTargets, R.id.news_flipper)
            }
            if (activeWidgetIds(applicationContext).isEmpty()) cancel(applicationContext)

            if (shouldRetry) Result.retry() else Result.success()
        }

    private fun refreshWidgets(appWidgetIds: IntArray): Boolean {
        val settings = SettingsStore(applicationContext)
        val store = NewsWidgetStore(applicationContext)
        val repository = NewsRepository()
        val cache = FeedCache(applicationContext)
        val backend = runCatching { settings.backendUrlBlocking() }.getOrDefault("")
        val perSourceCap = runCatching { settings.perSourceCapBlocking() }.getOrDefault(0)
        var shouldRetry = false

        appWidgetIds.forEach { appWidgetId ->
            val config = store.config(appWidgetId) ?: return@forEach
            val previous = store.snapshot(appWidgetId)
            KanarekWidgetProvider.updateStatus(
                context = applicationContext,
                appWidgetId = appWidgetId,
                status = NewsWidgetStatus.LOADING,
                lastUpdatedMillis = previous?.lastUpdatedMillis,
            )
            val fetchResult =
                runCatching {
                    repository.fetchBlockingWithStatus(
                        feeds = config.feeds,
                        backendUrl = backend,
                        limit = ITEM_CAP,
                        cache = cache,
                        perSourceCap = perSourceCap,
                    )
                }.getOrDefault(NewsFetchResult(items = emptyList(), successfulSources = 0))
            val outcome =
                widgetRefreshOutcome(
                    previous = previous,
                    fetched = fetchResult.items,
                    fetchSucceeded = fetchResult.successfulSources > 0,
                    nowMillis = System.currentTimeMillis(),
                )
            val committed =
                store.runIfCurrent(appWidgetId, config) {
                    if (outcome.saveSnapshot && outcome.snapshot != null) {
                        store.saveSnapshot(appWidgetId, outcome.snapshot)
                    }
                    KanarekWidgetProvider.updateStatus(
                        context = applicationContext,
                        appWidgetId = appWidgetId,
                        status =
                            if (outcome.shouldRetry) {
                                NewsWidgetStatus.ERROR
                            } else {
                                NewsWidgetStatus.READY
                            },
                        lastUpdatedMillis = outcome.snapshot?.lastUpdatedMillis,
                    )
                }
            if (committed && outcome.shouldRetry) shouldRetry = true
        }
        return shouldRetry
    }

    companion object {
        internal const val PERIODIC_WORK_NAME = "kanarek_widget_refresh"
        internal const val MANUAL_WORK_NAME = "kanarek_widget_refresh_now"
        private const val KEY_WIDGET_IDS = "widget_ids"
        private const val ITEM_CAP = 12
        private const val REFRESH_MINUTES = 30L
        private const val BACKOFF_SECONDS = 30L
        private val singleFlight = WidgetRefreshSingleFlight()

        fun reconcile(context: Context) {
            val activeIds = activeWidgetIds(context)
            when (WidgetRefreshPolicy.scheduleAction(activeIds)) {
                WidgetRefreshScheduleAction.ENSURE -> ensurePeriodic(context)
                WidgetRefreshScheduleAction.CANCEL -> cancel(context)
            }
        }

        fun refreshNow(
            context: Context,
            requestedWidgetIds: IntArray? = null,
        ) {
            val targets =
                WidgetRefreshPolicy.selectTargets(
                    requestedWidgetIds = requestedWidgetIds,
                    activeWidgetIds = activeWidgetIds(context),
                )
            if (targets.isEmpty()) {
                reconcile(context)
                return
            }
            val request =
                OneTimeWorkRequestBuilder<WidgetRefreshWorker>()
                    .setInputData(Data.Builder().putIntArray(KEY_WIDGET_IDS, targets).build())
                    .setConstraints(networkConstraints(requireBatteryNotLow = false))
                    .setBackoffCriteria(
                        BackoffPolicy.EXPONENTIAL,
                        BACKOFF_SECONDS,
                        TimeUnit.SECONDS,
                    ).build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                MANUAL_WORK_NAME,
                ExistingWorkPolicy.APPEND_OR_REPLACE,
                request,
            )
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).apply {
                cancelUniqueWork(PERIODIC_WORK_NAME)
                cancelUniqueWork(MANUAL_WORK_NAME)
            }
        }

        internal fun activeWidgetIds(context: Context): IntArray =
            AppWidgetManager.getInstance(context)
                .getAppWidgetIds(ComponentName(context, KanarekWidgetProvider::class.java))

        private fun ensurePeriodic(context: Context) {
            val request =
                PeriodicWorkRequestBuilder<WidgetRefreshWorker>(REFRESH_MINUTES, TimeUnit.MINUTES)
                    .setConstraints(networkConstraints(requireBatteryNotLow = true))
                    .setBackoffCriteria(
                        BackoffPolicy.EXPONENTIAL,
                        BACKOFF_SECONDS,
                        TimeUnit.SECONDS,
                    ).build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
        }

        private fun networkConstraints(requireBatteryNotLow: Boolean): Constraints =
            Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .setRequiresBatteryNotLow(requireBatteryNotLow)
                .build()
    }
}
