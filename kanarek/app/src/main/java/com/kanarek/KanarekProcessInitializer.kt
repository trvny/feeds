package com.kanarek

import android.content.Context
import androidx.startup.Initializer
import androidx.work.WorkManagerInitializer
import com.kanarek.data.NewsNotificationStore
import com.kanarek.data.SettingsStore
import com.kanarek.notifications.NewsNotificationWorker
import com.kanarek.reader.ReaderRefreshWorker
import com.kanarek.widget.WidgetRefreshWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class KanarekProcessInitializer : Initializer<Unit> {
    override fun create(context: Context) {
        val applicationContext = context.applicationContext
        WidgetRefreshWorker.reconcile(applicationContext)
        CoroutineScope(SupervisorJob() + Dispatchers.Default).launch {
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

    override fun dependencies(): List<Class<out Initializer<*>>> =
        listOf(WorkManagerInitializer::class.java)
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
