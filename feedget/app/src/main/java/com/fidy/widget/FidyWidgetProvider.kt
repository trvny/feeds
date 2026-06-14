package com.fidy.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import com.fidy.R

/**
 * Home-screen widget: a resizable, auto-advancing news slideshow.
 *
 * The slideshow is an [android.widget.AdapterViewFlipper] backed by
 * [NewsRemoteViewsService]; the launcher auto-advances it (autoAdvanceViewId in
 * the provider xml) and the flipper also self-starts. Tapping a card opens the
 * article; the refresh button re-pulls the feeds.
 */
class FidyWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { id -> renderWidget(context, manager, id) }
        WidgetRefreshWorker.schedule(context)
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        val manager = AppWidgetManager.getInstance(context)
        when (intent.action) {
            ACTION_REFRESH -> {
                val ids = widgetIds(context, manager, intent)
                manager.notifyAppWidgetViewDataChanged(ids, R.id.news_flipper)
            }
        }
    }

    override fun onEnabled(context: Context) {
        WidgetRefreshWorker.schedule(context)
    }

    override fun onDisabled(context: Context) {
        WidgetRefreshWorker.cancel(context)
    }

    private fun renderWidget(context: Context, manager: AppWidgetManager, appWidgetId: Int) {
        val views = android.widget.RemoteViews(context.packageName, R.layout.widget).apply {
            // Feed the slideshow from the collection service (unique data Uri per widget id).
            val serviceIntent = Intent(context, NewsRemoteViewsService::class.java).apply {
                putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                data = Uri.parse(toUri(Intent.URI_INTENT_SCHEME))
            }
            setRemoteAdapter(R.id.news_flipper, serviceIntent)
            setEmptyView(R.id.news_flipper, R.id.widget_empty)

            // Tapping a card opens its article. The per-item fill-in intent supplies the URL.
            val openTemplate = PendingIntent.getActivity(
                context,
                appWidgetId,
                Intent(Intent.ACTION_VIEW),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
            )
            setPendingIntentTemplate(R.id.news_flipper, openTemplate)

            // Refresh button.
            setOnClickPendingIntent(R.id.widget_refresh, refreshPendingIntent(context, appWidgetId))
        }

        manager.updateAppWidget(appWidgetId, views)
        manager.notifyAppWidgetViewDataChanged(appWidgetId, R.id.news_flipper)
    }

    private fun refreshPendingIntent(context: Context, appWidgetId: Int): PendingIntent {
        val intent = Intent(context, FidyWidgetProvider::class.java).apply {
            action = ACTION_REFRESH
            putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
            // Unique per widget so the PendingIntents don't collapse into one.
            data = Uri.parse("fidy://refresh/$appWidgetId")
        }
        return PendingIntent.getBroadcast(
            context,
            appWidgetId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun widgetIds(context: Context, manager: AppWidgetManager, intent: Intent): IntArray {
        val id = intent.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID)
        return if (id != AppWidgetManager.INVALID_APPWIDGET_ID) {
            intArrayOf(id)
        } else {
            manager.getAppWidgetIds(ComponentName(context, FidyWidgetProvider::class.java))
        }
    }

    companion object {
        const val ACTION_REFRESH = "com.fidy.action.REFRESH"

        /** Triggers a data refresh on every fidy widget on screen. */
        fun refreshAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, FidyWidgetProvider::class.java))
            if (ids.isNotEmpty()) manager.notifyAppWidgetViewDataChanged(ids, R.id.news_flipper)
        }
    }
}
