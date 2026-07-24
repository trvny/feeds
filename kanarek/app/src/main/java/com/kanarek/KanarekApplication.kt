package com.kanarek

import android.app.Application
import com.kanarek.data.NewsNotificationStore
import com.kanarek.data.SettingsStore
import com.kanarek.notifications.NewsNotificationWorker
import com.kanarek.reader.ReaderRefreshWorker
import com.kanarek.widget.WidgetRefreshWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class KanarekApplication : Application() {
    private val processScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        WidgetRefreshWorker.reconcile(applicationContext)
        processScope.launch {
            val settings = SettingsStore(applicationContext)
            val notifications = NewsNotificationStore(applicationContext)
            reconcilePersistedSchedules(
                state =
                    ProcessScheduleState(
                        readerRefreshMinutes = settings.backgroundRefreshMinutesNow(),
                        notificationsEnabled = notifications.configNow().enabled,
                    ),
                syncReader = { minutes ->
                    ReaderRefreshWorker.syncSchedule(applicationContext, minutes)
                },
                syncNotifications = { enabled ->
                    NewsNotificationWorker.syncSchedule(applicationContext, enabled)
                },
            )
        }
    }
}

internal data class ProcessScheduleState(
    val readerRefreshMinutes: Int,
    val notificationsEnabled: Boolean,
)

internal fun reconcilePersistedSchedules(
    state: ProcessScheduleState,
    syncReader: (Int) -> Unit,
    syncNotifications: (Boolean) -> Unit,
) {
    syncReader(state.readerRefreshMinutes)
    syncNotifications(state.notificationsEnabled)
}
