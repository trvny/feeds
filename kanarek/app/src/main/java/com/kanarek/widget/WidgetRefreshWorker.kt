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
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope

/** Fetches each active widget feed once and stores one shared snapshot. */
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

            val shouldRetry = refreshWidgets(targets)
            val remainingIds = activeWidgetIds(applicationContext)
            if (remainingIds.isNotEmpty()) {
                AppWidgetManager.getInstance(applicationContext)
                    .notifyAppWidgetViewDataChanged(remainingIds, R.id.news_flipper)
            } else {
                NewsWidgetStore(applicationContext).clearSharedSnapshot()
                cancel(applicationContext)
            }

            if (shouldRetry) Result.retry() else Result.success()
        }

    private suspend fun refreshWidgets(targetIds: IntArray): Boolean {
        val settings = SettingsStore(applicationContext)
        val store = NewsWidgetStore(applicationContext)
        val repository = NewsRepository()
        val cache = FeedCache(applicationContext)
        val backend = runCatching { settings.backendUrlBlocking() }.getOrDefault("")
        val initialConfigs = currentConfigs(store)
        val targetConfigs = targetIds.mapNotNull { id -> initialConfigs[id]?.let { id to it } }.toMap()
        val previous = store.sharedSnapshot()

        targetConfigs.forEach { (appWidgetId, config) ->
            store.runIfCurrent(appWidgetId, config) {
                KanarekWidgetProvider.updateStatus(
                    context = applicationContext,
                    appWidgetId = appWidgetId,
                    status = NewsWidgetStatus.LOADING,
                    lastUpdatedMillis = previous?.lastUpdatedMillis ?: store.snapshot(appWidgetId)?.lastUpdatedMillis,
                )
            }
        }

        val feeds = widgetFeedUnion(initialConfigs.values)
        if (feeds.isEmpty()) return false
        val results = fetchFeeds(feeds, repository, cache, backend)
        val finalConfigs = currentConfigs(store)
        val finalFeeds = widgetFeedUnion(finalConfigs.values)
        if (finalFeeds.isEmpty()) {
            store.clearSharedSnapshot()
            return false
        }

        val outcome =
            mergeSharedWidgetSnapshot(
                previous = previous,
                activeFeeds = finalFeeds,
                results = results,
                nowMillis = System.currentTimeMillis(),
            )
        outcome.snapshot?.let(store::saveSharedSnapshot)
        updateStatuses(store, targetConfigs, results, outcome.snapshot)
        return outcome.shouldRetry
    }

    private suspend fun fetchFeeds(
        feeds: List<String>,
        repository: NewsRepository,
        cache: FeedCache,
        backendUrl: String,
    ): List<FeedRefreshResult> =
        coroutineScope {
            feeds.map { feed ->
                async(Dispatchers.IO) {
                    val result =
                        runCatching {
                            repository.fetchBlockingWithStatus(
                                feeds = listOf(feed),
                                backendUrl = backendUrl,
                                limit = ITEM_CAP,
                                cache = cache,
                                perSourceCap = 0,
                            )
                        }.getOrDefault(NewsFetchResult(items = emptyList(), successfulSources = 0))
                    FeedRefreshResult(
                        feed = feed,
                        items = result.items,
                        successful = result.successfulSources > 0,
                    )
                }
            }.awaitAll()
        }

    private fun currentConfigs(store: NewsWidgetStore): Map<Int, NewsWidgetConfig> =
        activeWidgetIds(applicationContext)
            .mapNotNull { appWidgetId -> store.config(appWidgetId)?.let { appWidgetId to it } }
            .toMap()

    private fun updateStatuses(
        store: NewsWidgetStore,
        targetConfigs: Map<Int, NewsWidgetConfig>,
        results: List<FeedRefreshResult>,
        snapshot: SharedNewsWidgetSnapshot?,
    ) {
        val byFeed = results.associateBy(FeedRefreshResult::feed)
        targetConfigs.forEach { (appWidgetId, config) ->
            val attempted = config.feeds.map(String::trim).mapNotNull(byFeed::get)
            if (attempted.isEmpty()) return@forEach
            store.runIfCurrent(appWidgetId, config) {
                KanarekWidgetProvider.updateStatus(
                    context = applicationContext,
                    appWidgetId = appWidgetId,
                    status =
                        if (attempted.any(FeedRefreshResult::successful)) {
                            NewsWidgetStatus.READY
                        } else {
                            NewsWidgetStatus.ERROR
                        },
                    lastUpdatedMillis = snapshot?.lastUpdatedMillis,
                )
            }
        }
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
