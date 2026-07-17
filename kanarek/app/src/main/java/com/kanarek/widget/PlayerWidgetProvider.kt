package com.kanarek.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.RemoteViews
import androidx.core.content.ContextCompat
import com.kanarek.R
import com.kanarek.data.SettingsStore
import com.kanarek.data.Station
import com.kanarek.player.PlayerService

/**
 * Home-screen widget for background radio/IPTV playback: current station's logo + name, plus
 * play/pause/next/prev. Pure control surface — the [androidx.media3.exoplayer.ExoPlayer]/session
 * lives in [PlayerService]; button taps just message that service. Live updates (play state,
 * station changes) are pushed by the service via [updateAll], not polled —
 * `player_widget_info.xml` sets `updatePeriodMillis=0`. [onUpdate] only covers the cold-start
 * case (widget just added, service not running yet), rendering the last-known station at rest.
 */
class PlayerWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        ids: IntArray,
    ) {
        val settings = SettingsStore(context)
        val stations = runCatching { settings.stationsBlocking() }.getOrDefault(emptyList())
        val lastId = runCatching { settings.lastStationIdBlocking() }.getOrDefault(null)
        val station = stations.firstOrNull { it.id == lastId } ?: stations.firstOrNull()
        ids.forEach { render(context, manager, it, station, isPlaying = false) }
    }

    override fun onReceive(
        context: Context,
        intent: Intent,
    ) {
        super.onReceive(context, intent)
        val serviceAction =
            when (intent.action) {
                ACTION_TOGGLE -> PlayerService.ACTION_TOGGLE
                ACTION_NEXT -> PlayerService.ACTION_NEXT
                ACTION_PREV -> PlayerService.ACTION_PREV
                else -> return
            }
        val svc = Intent(context, PlayerService::class.java).setAction(serviceAction)
        ContextCompat.startForegroundService(context, svc)
    }

    companion object {
        const val ACTION_TOGGLE = "com.kanarek.player.widget.action.TOGGLE"
        const val ACTION_NEXT = "com.kanarek.player.widget.action.NEXT"
        const val ACTION_PREV = "com.kanarek.player.widget.action.PREV"

        /** Pushed by [PlayerService] whenever playback state or the current station changes. */
        fun updateAll(
            context: Context,
            station: Station?,
            isPlaying: Boolean,
        ) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, PlayerWidgetProvider::class.java))
            ids.forEach { id -> render(context, manager, id, station, isPlaying) }
        }

        private fun render(
            context: Context,
            manager: AppWidgetManager,
            appWidgetId: Int,
            station: Station?,
            isPlaying: Boolean,
        ) {
            val views =
                RemoteViews(context.packageName, R.layout.player_widget).apply {
                    setTextViewText(R.id.player_title, station?.name ?: context.getString(R.string.player_widget_empty))

                    val group = station?.groupTitle.orEmpty()
                    setTextViewText(R.id.player_subtitle, group)
                    setViewVisibility(R.id.player_subtitle, if (group.isBlank()) View.GONE else View.VISIBLE)

                    val logo = station?.logoUrl?.takeIf { it.isNotBlank() }?.let { WidgetImageCache.get(context, it) }
                    if (logo != null) {
                        setImageViewBitmap(R.id.player_logo, logo)
                    } else {
                        setImageViewResource(R.id.player_logo, R.drawable.ic_radio_fallback)
                    }

                    setImageViewResource(R.id.player_play_pause, if (isPlaying) R.drawable.ic_pause else R.drawable.ic_play)
                    setContentDescription(
                        R.id.player_play_pause,
                        context.getString(if (isPlaying) R.string.action_pause else R.string.action_play),
                    )

                    setOnClickPendingIntent(R.id.player_play_pause, widgetActionIntent(context, appWidgetId, ACTION_TOGGLE))
                    setOnClickPendingIntent(R.id.player_next, widgetActionIntent(context, appWidgetId, ACTION_NEXT))
                    setOnClickPendingIntent(R.id.player_prev, widgetActionIntent(context, appWidgetId, ACTION_PREV))
                    setOnClickPendingIntent(R.id.player_root, openAppIntent(context, appWidgetId))
                }
            manager.updateAppWidget(appWidgetId, views)
        }

        /** Explicit + immutable — a fixed always-the-same-effect button tap, not a per-item
         *  fill-in template, so it doesn't need the ArticleRedirectActivity-style trampoline. */
        private fun widgetActionIntent(
            context: Context,
            appWidgetId: Int,
            action: String,
        ): PendingIntent {
            val intent =
                Intent(context, PlayerWidgetProvider::class.java).apply {
                    this.action = action
                    data = Uri.parse("kanarek-player://$action/$appWidgetId")
                }
            return PendingIntent.getBroadcast(
                context,
                appWidgetId,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }

        private fun openAppIntent(
            context: Context,
            appWidgetId: Int,
        ): PendingIntent {
            val intent =
                Intent(context, com.kanarek.HomeActivity::class.java)
                    .putExtra(com.kanarek.HomeActivity.EXTRA_PAGE, com.kanarek.HomeActivity.PAGE_PLAYER)
            return PendingIntent.getActivity(
                context,
                appWidgetId,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }
    }
}
