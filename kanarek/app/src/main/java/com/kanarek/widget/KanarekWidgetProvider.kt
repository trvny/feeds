package com.kanarek.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.text.format.DateFormat
import android.util.TypedValue
import android.view.View
import android.widget.RemoteViews
import com.kanarek.R
import com.kanarek.data.NewsRepository
import com.kanarek.data.SettingsStore
import java.util.Date
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

internal enum class NewsWidgetStatus { LOADING, READY, ERROR }

private data class NewsWidgetRender(
    val appWidgetId: Int,
    val config: NewsWidgetConfig,
    val lastUpdatedMillis: Long?,
    val sizeClass: WidgetSizeClass,
)

/** Home-screen widget: a resizable, auto-advancing news slideshow. */
class KanarekWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        ids: IntArray,
    ) {
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val settings = SettingsStore(context)
                val global = readGlobalConfig(settings)
                val store = NewsWidgetStore(context)
                ids.forEach { id ->
                    val config = store.configOrMigrate(id, global)
                    store.runIfCurrent(id, config) {
                        renderWidget(
                            context,
                            manager,
                            NewsWidgetRender(
                                appWidgetId = id,
                                config = config,
                                lastUpdatedMillis = store.snapshot(id)?.lastUpdatedMillis,
                                sizeClass =
                                    widgetSizeClass(manager.getAppWidgetOptions(id)),
                            ),
                        )
                    }
                }
                WidgetRefreshWorker.reconcile(context)
                WidgetRefreshWorker.refreshNow(context, ids)
            } finally {
                pendingResult.finish()
            }
        }
    }

    override fun onAppWidgetOptionsChanged(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int,
        newOptions: Bundle,
    ) {
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val store = NewsWidgetStore(context)
                val config =
                    store.configOrMigrate(
                        appWidgetId,
                        readGlobalConfig(SettingsStore(context)),
                    )
                store.runIfCurrent(appWidgetId, config) {
                    renderWidget(
                        context,
                        appWidgetManager,
                        NewsWidgetRender(
                            appWidgetId = appWidgetId,
                            config = config,
                            lastUpdatedMillis =
                                store.snapshot(appWidgetId)?.lastUpdatedMillis,
                            sizeClass = widgetSizeClass(newOptions),
                        ),
                    )
                }
            } finally {
                pendingResult.finish()
            }
        }
    }

    override fun onEnabled(context: Context) {
        WidgetRefreshWorker.reconcile(context)
    }

    override fun onDisabled(context: Context) {
        WidgetRefreshWorker.cancel(context)
    }

    override fun onDeleted(
        context: Context,
        appWidgetIds: IntArray,
    ) {
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val store = NewsWidgetStore(context)
                appWidgetIds.forEach(store::delete)
                WidgetRefreshWorker.reconcile(context)
            } finally {
                pendingResult.finish()
            }
        }
    }

    private suspend fun readGlobalConfig(settings: SettingsStore): NewsWidgetConfig =
        NewsWidgetConfig(
            feeds =
                runCatching { settings.feeds.first() }
                    .getOrDefault(NewsRepository.DEFAULT_FEEDS),
            headlines =
                runCatching { settings.headlinesMode.first() }
                    .getOrDefault(false),
            intervalSeconds =
                runCatching { settings.intervalSeconds.first() }
                    .getOrDefault(SettingsStore.DEFAULT_INTERVAL),
        )

    private fun renderWidget(
        context: Context,
        manager: AppWidgetManager,
        render: NewsWidgetRender,
    ) {
        val views =
            buildViews(
                context = context,
                appWidgetId = render.appWidgetId,
                config = render.config,
                lastUpdatedMillis = render.lastUpdatedMillis,
                sizeClass = render.sizeClass,
            )
        manager.updateAppWidget(render.appWidgetId, views)
        manager.notifyAppWidgetViewDataChanged(render.appWidgetId, R.id.news_flipper)
    }

    internal fun buildViews(
        context: Context,
        appWidgetId: Int,
        config: NewsWidgetConfig,
        lastUpdatedMillis: Long?,
        sizeClass: WidgetSizeClass = WidgetSizeClass.REGULAR,
    ): RemoteViews {
        val views =
            RemoteViews(context.packageName, R.layout.widget).apply {
                val serviceIntent =
                    Intent(context, NewsRemoteViewsService::class.java).apply {
                        putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                        data = Uri.parse(toUri(Intent.URI_INTENT_SCHEME))
                    }
                setRemoteAdapter(R.id.news_flipper, serviceIntent)
                setEmptyView(R.id.news_flipper, R.id.widget_empty)
                setInt(R.id.news_flipper, "setFlipInterval", config.intervalSeconds * 1_000)

                val openTemplate =
                    PendingIntent.getActivity(
                        context,
                        appWidgetId,
                        Intent(context, ArticleRedirectActivity::class.java),
                        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
                    )
                setPendingIntentTemplate(R.id.news_flipper, openTemplate)
                setOnClickPendingIntent(
                    R.id.widget_refresh,
                    actionPendingIntent(context, appWidgetId, ACTION_REFRESH, "refresh"),
                )
                setOnClickPendingIntent(
                    R.id.widget_previous,
                    actionPendingIntent(
                        context,
                        appWidgetId,
                        ACTION_SHOW_PREVIOUS,
                        "previous",
                    ),
                )
                setOnClickPendingIntent(
                    R.id.widget_next,
                    actionPendingIntent(context, appWidgetId, ACTION_SHOW_NEXT, "next"),
                )
                applyStatus(
                    context = context,
                    views = this,
                    status =
                        if (lastUpdatedMillis == null) {
                            NewsWidgetStatus.LOADING
                        } else {
                            NewsWidgetStatus.READY
                        },
                    lastUpdatedMillis = lastUpdatedMillis,
                )
                applyWidgetSize(this, sizeClass)
            }
        return views
    }

    private fun actionPendingIntent(
        context: Context,
        appWidgetId: Int,
        actionName: String,
        path: String,
    ): PendingIntent {
        val intent =
            Intent(context, WidgetActionReceiver::class.java).apply {
                action = actionName
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                data = Uri.parse("kanarek://$path/$appWidgetId")
            }
        return PendingIntent.getBroadcast(
            context,
            (appWidgetId * 10) + path.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    companion object {
        const val ACTION_REFRESH = "com.kanarek.action.REFRESH"
        const val ACTION_SHOW_PREVIOUS = "com.kanarek.action.SHOW_PREVIOUS"
        const val ACTION_SHOW_NEXT = "com.kanarek.action.SHOW_NEXT"

        fun update(
            context: Context,
            appWidgetId: Int,
        ) {
            context.sendBroadcast(
                Intent(context, KanarekWidgetProvider::class.java).apply {
                    action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                    putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, intArrayOf(appWidgetId))
                },
            )
        }

        fun updateAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids =
                manager.getAppWidgetIds(
                    ComponentName(context, KanarekWidgetProvider::class.java),
                )
            if (ids.isEmpty()) return
            context.sendBroadcast(
                Intent(context, KanarekWidgetProvider::class.java).apply {
                    action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                    putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
                },
            )
        }

        fun refreshAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids =
                manager.getAppWidgetIds(
                    ComponentName(context, KanarekWidgetProvider::class.java),
                )
            if (ids.isNotEmpty()) {
                manager.notifyAppWidgetViewDataChanged(ids, R.id.news_flipper)
            }
        }

        internal fun updateStatus(
            context: Context,
            appWidgetId: Int,
            status: NewsWidgetStatus,
            lastUpdatedMillis: Long?,
        ) {
            if (appWidgetId == AppWidgetManager.INVALID_APPWIDGET_ID) return
            val manager = AppWidgetManager.getInstance(context)
            val views =
                RemoteViews(context.packageName, R.layout.widget).apply {
                    applyStatus(context, this, status, lastUpdatedMillis)
                    applyWidgetSize(
                        views = this,
                        sizeClass = widgetSizeClass(manager.getAppWidgetOptions(appWidgetId)),
                    )
                }
            manager.partiallyUpdateAppWidget(appWidgetId, views)
        }

        private fun applyWidgetSize(
            views: RemoteViews,
            sizeClass: WidgetSizeClass,
        ) {
            views.setViewVisibility(
                R.id.widget_status,
                if (sizeClass == WidgetSizeClass.COMPACT) View.GONE else View.VISIBLE,
            )
            views.setViewVisibility(
                R.id.widget_previous,
                if (sizeClass == WidgetSizeClass.COMPACT) View.GONE else View.VISIBLE,
            )
            views.setViewVisibility(R.id.widget_refresh, View.VISIBLE)
            views.setViewVisibility(R.id.widget_next, View.VISIBLE)
            val emptyTextSize =
                when (sizeClass) {
                    WidgetSizeClass.COMPACT -> 11f
                    WidgetSizeClass.REGULAR -> 13f
                    WidgetSizeClass.EXPANDED -> 15f
                }
            val statusTextSize =
                when (sizeClass) {
                    WidgetSizeClass.COMPACT -> 9f
                    WidgetSizeClass.REGULAR -> 10f
                    WidgetSizeClass.EXPANDED -> 11f
                }
            views.setTextViewTextSize(
                R.id.widget_empty,
                TypedValue.COMPLEX_UNIT_SP,
                emptyTextSize,
            )
            views.setTextViewTextSize(
                R.id.widget_status,
                TypedValue.COMPLEX_UNIT_SP,
                statusTextSize,
            )
        }

        private fun applyStatus(
            context: Context,
            views: RemoteViews,
            status: NewsWidgetStatus,
            lastUpdatedMillis: Long?,
        ) {
            val time =
                lastUpdatedMillis
                    ?.takeIf { it > 0L }
                    ?.let { DateFormat.getTimeFormat(context).format(Date(it)) }
            val statusText =
                when {
                    status == NewsWidgetStatus.LOADING && time != null ->
                        context.getString(R.string.widget_status_refreshing, time)
                    status == NewsWidgetStatus.LOADING ->
                        context.getString(R.string.widget_status_loading)
                    status == NewsWidgetStatus.READY && time != null ->
                        context.getString(R.string.widget_status_updated, time)
                    status == NewsWidgetStatus.ERROR && time != null ->
                        context.getString(R.string.widget_status_error_with_time, time)
                    else ->
                        context.getString(R.string.widget_status_error)
                }
            val emptyText =
                if (status == NewsWidgetStatus.ERROR) {
                    context.getString(R.string.widget_status_error)
                } else {
                    context.getString(R.string.widget_status_loading)
                }
            views.setTextViewText(R.id.widget_status, statusText)
            views.setViewVisibility(R.id.widget_status, View.VISIBLE)
            views.setTextViewText(R.id.widget_empty, emptyText)
        }
    }
}
