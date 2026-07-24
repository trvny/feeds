package com.kanarek.notifications

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.kanarek.HomeActivity
import com.kanarek.R
import com.kanarek.data.FeedCache
import com.kanarek.data.NewsItem
import com.kanarek.data.NewsNotificationStore
import com.kanarek.data.NewsRepository
import com.kanarek.data.SettingsStore
import java.time.LocalTime
import java.util.concurrent.TimeUnit

class NewsNotificationWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val store = NewsNotificationStore(applicationContext)
        val config = store.configNow()
        return if (config.enabled) syncEnabled(store) else Result.success()
    }

    private suspend fun syncEnabled(store: NewsNotificationStore): Result {
        val settings = SettingsStore(applicationContext)
        val currentConfig = store.reconcileConfiguredFeeds(settings.feedsNow())
        if (!currentConfig.enabled) return Result.success()
        val feeds = currentConfig.selectedFeeds
        if (feeds.isEmpty()) return Result.success()
        val fetchResult =
            runCatching {
                NewsRepository().fetch(
                    feeds = feeds,
                    backendUrl = settings.backendUrlNow(),
                    limit = FETCH_LIMIT,
                    cache = FeedCache(applicationContext),
                )
            }
        if (fetchResult.isFailure) return Result.retry()
        val items = fetchResult.getOrThrow()

        val now = LocalTime.now()
        val decision =
            store.recordFetch(
                expectedConfig = currentConfig,
                items = items,
                minuteOfDay = now.hour * 60 + now.minute,
            ) ?: return Result.success()
        if (decision.shouldNotify && canPostNotifications(applicationContext)) {
            postNotification(applicationContext, decision.newItems)
        }
        return Result.success()
    }

    companion object {
        private const val WORK_NAME = "kanarek_news_notifications"
        private const val CHANNEL_ID = "news_updates"
        private const val NOTIFICATION_ID = 2_201
        private const val FETCH_LIMIT = 100

        fun syncSchedule(
            context: Context,
            enabled: Boolean,
        ) {
            val workManager = WorkManager.getInstance(context.applicationContext)
            if (!enabled) {
                workManager.cancelUniqueWork(WORK_NAME)
                NotificationManagerCompat.from(context).cancel(NOTIFICATION_ID)
                return
            }
            val request =
                PeriodicWorkRequestBuilder<NewsNotificationWorker>(1, TimeUnit.HOURS)
                    .setConstraints(
                        Constraints
                            .Builder()
                            .setRequiredNetworkType(NetworkType.CONNECTED)
                            .setRequiresBatteryNotLow(true)
                            .build(),
                    ).setBackoffCriteria(
                        BackoffPolicy.EXPONENTIAL,
                        15,
                        TimeUnit.MINUTES,
                    ).build()
            workManager.enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
        }

        private fun canPostNotifications(context: Context): Boolean {
            val permissionGranted =
                Build.VERSION.SDK_INT < 33 ||
                    ContextCompat.checkSelfPermission(
                        context,
                        Manifest.permission.POST_NOTIFICATIONS,
                    ) == PackageManager.PERMISSION_GRANTED
            return permissionGranted &&
                NotificationManagerCompat.from(context).areNotificationsEnabled()
        }

        @SuppressLint("MissingPermission")
        private fun postNotification(
            context: Context,
            items: List<NewsItem>,
        ) {
            if (items.isEmpty()) return
            createChannel(context)
            val count = items.size
            val title =
                context.resources.getQuantityString(
                    R.plurals.news_notification_count,
                    count,
                    count,
                )
            val notification =
                NotificationCompat
                    .Builder(context, CHANNEL_ID)
                    .setSmallIcon(R.drawable.ic_notification_news)
                    .setContentTitle(title)
                    .setContentText(items.first().title.trim().take(MAX_TITLE_LENGTH))
                    .setStyle(inboxStyle(context, title, items))
                    .setContentIntent(readerPendingIntent(context))
                    .setAutoCancel(true)
                    .setCategory(NotificationCompat.CATEGORY_RECOMMENDATION)
                    .setNumber(count)
                    .build()
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, notification)
        }

        private fun inboxStyle(
            context: Context,
            title: String,
            items: List<NewsItem>,
        ): NotificationCompat.InboxStyle {
            val style =
                NotificationCompat.InboxStyle()
                    .setBigContentTitle(title)
                    .setSummaryText(context.getString(R.string.news_notification_summary))
            items.take(5).forEach { item ->
                val itemTitle = item.title.trim().take(MAX_TITLE_LENGTH)
                val line =
                    item.source
                        .trim()
                        .take(MAX_SOURCE_LENGTH)
                        .takeIf(String::isNotBlank)
                        ?.let { "$it · $itemTitle" }
                        ?: itemTitle
                style.addLine(line)
            }
            return style
        }

        private fun readerPendingIntent(context: Context): PendingIntent {
            val intent =
                Intent(context, HomeActivity::class.java)
                    .putExtra(HomeActivity.EXTRA_PAGE, HomeActivity.PAGE_READER)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            return PendingIntent.getActivity(
                context,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }

        private fun createChannel(context: Context) {
            val manager = context.getSystemService(NotificationManager::class.java)
            val channel =
                NotificationChannel(
                    CHANNEL_ID,
                    context.getString(R.string.news_notification_channel),
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = context.getString(R.string.news_notification_channel_description)
                }
            manager.createNotificationChannel(channel)
        }

        private const val MAX_TITLE_LENGTH = 180
        private const val MAX_SOURCE_LENGTH = 60
    }
}
