package com.kanarek.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import com.kanarek.R
import com.kanarek.data.SettingsStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Home-screen widget: a resizable, auto-advancing news slideshow.
 *
 * The slideshow is an [android.widget.AdapterViewFlipper] backed by
 * [NewsRemoteViewsService]; the launcher auto-advances it (autoAdvanceViewId in
 * the provider xml) and the flipper also self-starts. Tapping a card opens the
 * article; the refresh button re-pulls the feeds.
 */
class KanarekWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        ids: IntArray,
    ) {
        val pendingResult = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val interval =
                    runCatching { SettingsStore(context).intervalSeconds.first() }
                        .getOrDefault(SettingsStore.DEFAULT_INTERVAL)
                ids.forEach { id -> renderWidget(context, manager, id, interval) }
                WidgetRefreshWorker.schedule(context)
            } finally {
                pendingResult.finish()
            }
        }
    }

    override fun onEnabled(context: Context) {
        WidgetRefreshWorker.schedule(context)
    }

    override fun onDisabled(context: Context) {
        WidgetRefreshWorker.cancel(context)
    }

    private fun renderWidget(
        context: Context,
        manager: AppWidgetManager,
        appWidgetId: Int,
        intervalSeconds: Int,
    ) {
        val views =
            android.widget.RemoteViews(context.packageName, R.layout.widget).apply {
                // Feed the slideshow from the collection service (unique data Uri per widget id).
                val serviceIntent =
                    Intent(context, NewsRemoteViewsService::class.java).apply {
                        putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                        data = Uri.parse(toUri(Intent.URI_INTENT_SCHEME))
                    }
                setRemoteAdapter(R.id.news_flipper, serviceIntent)
                setEmptyView(R.id.news_flipper, R.id.widget_empty)
                setInt(R.id.news_flipper, "setFlipInterval", intervalSeconds.coerceIn(3, 120) * 1_000)

                // Tapping a card opens its article. The template targets an explicit trampoline
                // (ArticleRedirectActivity) so the mutable PendingIntent is Android 14+-legal; the
                // per-item fill-in intent supplies the article URL as data.
                val openTemplate =
                    PendingIntent.getActivity(
                        context,
                        appWidgetId,
                        Intent(context, ArticleRedirectActivity::class.java),
                        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
                    )
                setPendingIntentTemplate(R.id.news_flipper, openTemplate)

                // Refresh button. The target receiver is unexported, so only this PendingIntent can
                // trigger the custom action; the exported AppWidgetProvider handles system updates.
                setOnClickPendingIntent(R.id.widget_refresh, actionPendingIntent(context, appWidgetId, ACTION_REFRESH, "refresh"))
                setOnClickPendingIntent(R.id.widget_previous, actionPendingIntent(context, appWidgetId, ACTION_SHOW_PREVIOUS, "previous"))
                setOnClickPendingIntent(R.id.widget_next, actionPendingIntent(context, appWidgetId, ACTION_SHOW_NEXT, "next"))
            }

        manager.updateAppWidget(appWidgetId, views)
        manager.notifyAppWidgetViewDataChanged(appWidgetId, R.id.news_flipper)
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
                // Unique per action and widget so PendingIntents cannot collapse into one.
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

        /** Re-renders every news widget, including slideshow controls and interval. */
        fun updateAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, KanarekWidgetProvider::class.java))
            if (ids.isEmpty()) return
            context.sendBroadcast(
                Intent(context, KanarekWidgetProvider::class.java).apply {
                    action = AppWidgetManager.ACTION_APPWIDGET_UPDATE
                    putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
                },
            )
        }

        /** Triggers a data refresh on every kanarek widget on screen. */
        fun refreshAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, KanarekWidgetProvider::class.java))
            if (ids.isNotEmpty()) manager.notifyAppWidgetViewDataChanged(ids, R.id.news_flipper)
        }
    }
}
