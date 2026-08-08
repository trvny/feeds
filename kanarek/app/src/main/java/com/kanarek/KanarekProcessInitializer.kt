package com.kanarek

import android.content.Context
import androidx.startup.Initializer
import androidx.work.WorkManagerInitializer
import coil.Coil
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.decode.SvgDecoder
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
        // Coil decodes no SVG unless the decoder is registered. Some logos in the
        // bundled and imported playlists are SVG, and without this AsyncImage
        // fails them and falls through Favicons.logoChain to a generic favicon.
        // The factory is lazy, so this costs nothing until the first image loads.
        // Note this covers Compose only: PlayerService decodes widget and
        // notification artwork itself with BitmapFactory, which still cannot
        // read SVG.
        // This is the process-wide loader and it wins over an Application
        // implementing ImageLoaderFactory, so customise it here - a factory
        // added on an Application class later would be silently ignored.
        Coil.setImageLoader(
            object : ImageLoaderFactory {
                override fun newImageLoader(): ImageLoader =
                    ImageLoader
                        .Builder(applicationContext)
                        .components { add(SvgDecoder.Factory()) }
                        .build()
            },
        )
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
