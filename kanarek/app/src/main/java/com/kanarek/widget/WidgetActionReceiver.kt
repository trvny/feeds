package com.kanarek.widget

import android.appwidget.AppWidgetManager
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.kanarek.R
import com.kanarek.player.PlayerService

/**
 * Private receiver for actions created by Kanarek's own widget PendingIntents.
 *
 * The AppWidgetProvider receivers must stay exported so the launcher can update them, but custom
 * refresh/playback actions do not need to be public. Keeping those actions on this unexported
 * receiver prevents other apps from refreshing the widget or controlling playback by sending a
 * matching broadcast directly.
 */
class WidgetActionReceiver : BroadcastReceiver() {
    override fun onReceive(
        context: Context,
        intent: Intent,
    ) {
        when (intent.action) {
            KanarekWidgetProvider.ACTION_REFRESH -> refreshNewsWidget(context, intent)
            PlayerWidgetProvider.ACTION_TOGGLE -> startPlayer(context, PlayerService.ACTION_TOGGLE)
            PlayerWidgetProvider.ACTION_NEXT -> startPlayer(context, PlayerService.ACTION_NEXT)
            PlayerWidgetProvider.ACTION_PREV -> startPlayer(context, PlayerService.ACTION_PREV)
        }
    }

    private fun refreshNewsWidget(
        context: Context,
        intent: Intent,
    ) {
        val manager = AppWidgetManager.getInstance(context)
        val id = intent.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID)
        val ids =
            if (id != AppWidgetManager.INVALID_APPWIDGET_ID) {
                intArrayOf(id)
            } else {
                manager.getAppWidgetIds(ComponentName(context, KanarekWidgetProvider::class.java))
            }
        if (ids.isNotEmpty()) manager.notifyAppWidgetViewDataChanged(ids, R.id.news_flipper)
    }

    private fun startPlayer(
        context: Context,
        action: String,
    ) {
        val service = Intent(context, PlayerService::class.java).setAction(action)
        ContextCompat.startForegroundService(context, service)
    }
}
