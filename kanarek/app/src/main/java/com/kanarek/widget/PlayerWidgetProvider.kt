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

/** Home-screen controls for the background Player service. */
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
                    if (saved != null && saved.station?.id == station?.id) {
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
        render(context, appWidgetManager, appWidgetId, state, widgetSizeClass(newOptions))
    }

    companion object {
        const val ACTION_TOGGLE = "com.kanarek.player.widget.action.TOGGLE"
        const val ACTION_NEXT = "com.kanarek.player.widget.action.NEXT"
        const val ACTION_PREV = "com.kanarek.player.widget.action.PREV"

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

        internal fun buildViews(
            context: Context,
            appWidgetId: Int,
            state: PlayerWidgetState,
            sizeClass: WidgetSizeClass = WidgetSizeClass.REGULAR,
        ): RemoteViews =
            RemoteViews(context.packageName, playerWidgetLayout(sizeClass)).apply {
                applyText(context, state, sizeClass)
                applyLogo(context, state.station)
                applyActions(context, appWidgetId, state, sizeClass)
                setOnClickPendingIntent(R.id.player_root, openAppIntent(context, appWidgetId))
            }

        private fun RemoteViews.applyText(
            context: Context,
            state: PlayerWidgetState,
            sizeClass: WidgetSizeClass,
        ) {
            val subtitle = playerWidgetSubtitle(state)
            val stationName = state.station?.name ?: context.getString(R.string.player_widget_empty)
            val title =
                if (sizeClass == WidgetSizeClass.COMPACT) {
                    subtitle.takeIf(String::isNotBlank) ?: stationName
                } else {
                    stationName
                }
            setTextViewText(R.id.player_title, title)
            if (sizeClass != WidgetSizeClass.COMPACT) {
                setTextViewText(R.id.player_subtitle, subtitle)
                setViewVisibility(
                    R.id.player_subtitle,
                    if (subtitle.isBlank()) View.GONE else View.VISIBLE,
                )
            }
        }

        private fun RemoteViews.applyLogo(
            context: Context,
            station: Station?,
        ) {
            val logo =
                station
                    ?.logoUrl
                    ?.takeIf(String::isNotBlank)
                    ?.let { WidgetImageCache.get(context, it) }
            if (logo != null) {
                setImageViewBitmap(R.id.player_logo, logo)
            } else {
                setImageViewResource(R.id.player_logo, R.drawable.ic_radio_fallback)
            }
        }

        private fun RemoteViews.applyActions(
            context: Context,
            appWidgetId: Int,
            state: PlayerWidgetState,
            sizeClass: WidgetSizeClass,
        ) {
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
            setContentDescription(R.id.player_play_pause, context.getString(actionDescription))
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
        }

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
