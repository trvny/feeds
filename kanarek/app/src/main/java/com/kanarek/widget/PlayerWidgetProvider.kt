package com.kanarek.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.RemoteViews
import com.kanarek.R
import com.kanarek.data.SettingsStore
import com.kanarek.data.Station
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

internal data class PlayerWidgetState(
    val station: Station?,
    val isPlaying: Boolean,
    val errorText: String? = null,
    val nowPlaying: String? = null,
)

internal fun playerWidgetSubtitle(state: PlayerWidgetState): String =
    state.errorText?.takeIf(String::isNotBlank)
        ?: state.nowPlaying?.takeIf(String::isNotBlank)
        ?: state.station?.groupTitle.orEmpty()

/**
 * Home-screen widget for background radio/IPTV playback: current station's logo + name, plus
 * play/pause/next/prev. Pure control surface — the [androidx.media3.exoplayer.ExoPlayer]/session
 * lives in [com.kanarek.player.PlayerService]; button taps just message that service through the
 * private [WidgetActionReceiver]. Live updates (play state, station changes) are pushed by the
 * service via [updateAll], not polled — `player_widget_info.xml` sets `updatePeriodMillis=0`.
 * A system update reads DataStore under [BroadcastReceiver.goAsync], never on the main thread.
 */
class PlayerWidgetProvider : AppWidgetProvider() {
    override fun onReceive(
        context: Context,
        intent: Intent,
    ) {
        if (intent.action != AppWidgetManager.ACTION_APPWIDGET_UPDATE) {
            super.onReceive(context, intent)
            return
        }

        val manager = AppWidgetManager.getInstance(context)
        val ids =
            intent.getIntArrayExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS)
                ?: manager.getAppWidgetIds(ComponentName(context, PlayerWidgetProvider::class.java))
        if (ids.isEmpty()) return

        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                val settings = SettingsStore(context.applicationContext)
                val stations = runCatching { settings.stationsNow() }.getOrDefault(emptyList())
                val lastId = runCatching { settings.lastStationIdNow() }.getOrDefault(null)
                val station = stations.firstOrNull { it.id == lastId } ?: stations.firstOrNull()
                val store = PlayerWidgetStateStore(context)
                val saved = store.load()
                val state =
                    if (saved?.station?.id == station?.id) {
                        saved.copy(station = station)
                    } else {
                        PlayerWidgetState(station = station, isPlaying = false)
                    }
                store.save(state)
                ids.forEach { render(context, manager, it, state) }
            } finally {
                pending.finish()
            }
        }
    }

    override fun onAppWidgetOptionsChanged(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int,
        newOptions: Bundle,
    ) {
        val state =
            PlayerWidgetStateStore(context).load()
                ?: PlayerWidgetState(station = null, isPlaying = false)
        render(
            context = context,
            manager = appWidgetManager,
            appWidgetId = appWidgetId,
            state = state,
            sizeClass = widgetSizeClass(newOptions),
        )
    }

    companion object {
        const val ACTION_TOGGLE = "com.kanarek.player.widget.action.TOGGLE"
        const val ACTION_NEXT = "com.kanarek.player.widget.action.NEXT"
        const val ACTION_PREV = "com.kanarek.player.widget.action.PREV"

        /** Pushed by [com.kanarek.player.PlayerService] whenever playback state or the current station changes. */
        fun updateAll(
            context: Context,
            station: Station?,
            isPlaying: Boolean,
            errorText: String? = null,
            nowPlaying: String? = null,
        ) {
            val state = PlayerWidgetState(station, isPlaying, errorText, nowPlaying)
            PlayerWidgetStateStore(context).save(state)
            val manager = AppWidgetManager.getInstance(context)
            val ids =
                manager.getAppWidgetIds(
                    ComponentName(context, PlayerWidgetProvider::class.java),
                )
            ids.forEach { id -> render(context, manager, id, state) }
        }

        private fun render(
            context: Context,
            manager: AppWidgetManager,
            appWidgetId: Int,
            state: PlayerWidgetState,
            sizeClass: WidgetSizeClass =
                widgetSizeClass(manager.getAppWidgetOptions(appWidgetId)),
        ) {
            manager.updateAppWidget(
                appWidgetId,
                buildViews(context, appWidgetId, state, sizeClass),
            )
        }

        /**
         * Builds the widget tree without touching [AppWidgetManager], so the whole render path
         * (resources, string formatting, every PendingIntent) is reachable from a unit test.
         */
        internal fun buildViews(
            context: Context,
            appWidgetId: Int,
            state: PlayerWidgetState,
            sizeClass: WidgetSizeClass = WidgetSizeClass.REGULAR,
        ): RemoteViews {
            val station = state.station
            val subtitle = playerWidgetSubtitle(state)
            return RemoteViews(context.packageName, playerWidgetLayout(sizeClass)).apply {
                val title =
                    if (sizeClass == WidgetSizeClass.COMPACT) {
                        subtitle.takeIf(String::isNotBlank)
                            ?: station?.name
                            ?: context.getString(R.string.player_widget_empty)
                    } else {
                        station?.name ?: context.getString(R.string.player_widget_empty)
                    }
                setTextViewText(R.id.player_title, title)

                if (sizeClass != WidgetSizeClass.COMPACT) {
                    setTextViewText(R.id.player_subtitle, subtitle)
                    setViewVisibility(
                        R.id.player_subtitle,
                        if (subtitle.isBlank()) View.GONE else View.VISIBLE,
                    )
                }

                val logo =
                    station
                        ?.logoUrl
                        ?.takeIf { it.isNotBlank() }
                        ?.let { WidgetImageCache.get(context, it) }
                if (logo != null) {
                    setImageViewBitmap(R.id.player_logo, logo)
                } else {
                    setImageViewResource(R.id.player_logo, R.drawable.ic_radio_fallback)
                }

                setImageViewResource(
                    R.id.player_play_pause,
                    if (state.isPlaying) R.drawable.ic_pause else R.drawable.ic_play,
                )
                val actionDescription =
                    when {
                        state.errorText != null -> R.string.action_retry
                        state.isPlaying -> R.string.action_pause
                        else -> R.string.action_play
                    }
                setContentDescription(
                    R.id.player_play_pause,
                    context.getString(actionDescription),
                )

                setOnClickPendingIntent(
                    R.id.player_play_pause,
                    widgetActionIntent(context, appWidgetId, ACTION_TOGGLE),
                )
                if (sizeClass != WidgetSizeClass.COMPACT) {
                    setOnClickPendingIntent(
                        R.id.player_next,
                        widgetActionIntent(context, appWidgetId, ACTION_NEXT),
                    )
                    setOnClickPendingIntent(
                        R.id.player_prev,
                        widgetActionIntent(context, appWidgetId, ACTION_PREV),
                    )
                }
                setOnClickPendingIntent(R.id.player_root, openAppIntent(context, appWidgetId))
            }
        }

        /** Explicit + immutable — a fixed always-the-same-effect button tap. The explicit target is
         *  unexported, so another app cannot invoke the same playback actions with a forged broadcast. */
        private fun widgetActionIntent(
            context: Context,
            appWidgetId: Int,
            action: String,
        ): PendingIntent {
            val intent =
                Intent(context, WidgetActionReceiver::class.java).apply {
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
                    .putExtra(
                        com.kanarek.HomeActivity.EXTRA_PAGE,
                        com.kanarek.HomeActivity.PAGE_PLAYER,
                    )
            return PendingIntent.getActivity(
                context,
                appWidgetId,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }
    }
}
