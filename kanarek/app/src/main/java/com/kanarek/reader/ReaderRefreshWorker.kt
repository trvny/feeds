package com.kanarek.reader

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.kanarek.data.ReaderBackgroundRefresh
import com.kanarek.data.ReaderFeedSyncConfig
import com.kanarek.data.ReaderFeedSynchronizer
import com.kanarek.data.ReaderRefreshScheduleAction
import com.kanarek.data.SettingsStore
import java.util.concurrent.TimeUnit

class ReaderRefreshWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val settings = SettingsStore(applicationContext)
        val interval = settings.backgroundRefreshMinutesNow()
        if (ReaderBackgroundRefresh.scheduleAction(interval) == ReaderRefreshScheduleAction.CANCEL) {
            cancel(applicationContext)
            return Result.success()
        }
        val result =
            ReaderFeedSynchronizer(applicationContext).refresh(
                config =
                    ReaderFeedSyncConfig(
                        feeds = settings.feedsNow(),
                        backendUrl = settings.backendUrlNow(),
                        perSourceCap = settings.perSourceCapNow(),
                    ),
                limit = READER_ITEM_LIMIT,
            )
        return if (result.shouldRetry) Result.retry() else Result.success()
    }

    companion object {
        internal const val WORK_NAME = "kanarek_reader_background_refresh"
        private const val READER_ITEM_LIMIT = 15
        private const val BACKOFF_MINUTES = 15L

        fun syncSchedule(
            context: Context,
            minutes: Int,
        ) {
            val normalized = ReaderBackgroundRefresh.normalize(minutes)
            val workManager = WorkManager.getInstance(context.applicationContext)
            when (ReaderBackgroundRefresh.scheduleAction(normalized)) {
                ReaderRefreshScheduleAction.CANCEL -> workManager.cancelUniqueWork(WORK_NAME)
                ReaderRefreshScheduleAction.SCHEDULE -> {
                    val request =
                        PeriodicWorkRequestBuilder<ReaderRefreshWorker>(
                            normalized.toLong(),
                            TimeUnit.MINUTES,
                        ).setConstraints(
                            Constraints
                                .Builder()
                                .setRequiredNetworkType(NetworkType.CONNECTED)
                                .setRequiresBatteryNotLow(true)
                                .build(),
                        ).setBackoffCriteria(
                            BackoffPolicy.EXPONENTIAL,
                            BACKOFF_MINUTES,
                            TimeUnit.MINUTES,
                        ).build()
                    workManager.enqueueUniquePeriodicWork(
                        WORK_NAME,
                        ExistingPeriodicWorkPolicy.UPDATE,
                        request,
                    )
                }
            }
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context.applicationContext).cancelUniqueWork(WORK_NAME)
        }
    }
}
