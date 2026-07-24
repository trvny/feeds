package com.kanarek.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.kanarek.R
import com.kanarek.data.BackupFormatException
import com.kanarek.data.BackupTooLargeException
import com.kanarek.data.PortableBackupCodec
import com.kanarek.data.PortableBackupManager
import com.kanarek.data.readBytesCapped
import com.kanarek.notifications.NewsNotificationWorker
import com.kanarek.widget.KanarekWidgetProvider
import com.kanarek.widget.PlayerWidgetProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException

@Composable
internal fun BackupControls(
    enabled: Boolean,
    onBusyChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val manager = remember(context) { PortableBackupManager(context.applicationContext) }
    var busy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) }

    fun setBusy(value: Boolean) {
        busy = value
        onBusyChange(value)
    }

    val exportLauncher =
        rememberLauncherForActivityResult(
            ActivityResultContracts.CreateDocument("application/xml"),
        ) { uri ->
            uri ?: return@rememberLauncherForActivityResult
            scope.launch {
                setBusy(true)
                status = null
                status =
                    try {
                        val bytes = manager.exportBytes()
                        withContext(Dispatchers.IO) {
                            val output =
                                context.contentResolver.openOutputStream(uri)
                                    ?: throw IOException("Could not open backup destination")
                            output.use { it.write(bytes) }
                        }
                        context.getString(R.string.backup_exported)
                    } catch (_: Exception) {
                        context.getString(R.string.backup_export_failed)
                    } finally {
                        setBusy(false)
                    }
            }
        }

    val importLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            uri ?: return@rememberLauncherForActivityResult
            scope.launch {
                setBusy(true)
                status = null
                status =
                    try {
                        val bytes =
                            withContext(Dispatchers.IO) {
                                val input =
                                    context.contentResolver.openInputStream(uri)
                                        ?: throw IOException("Could not open backup")
                                input.use {
                                    it.readBytesCapped(PortableBackupCodec.MAX_FILE_BYTES)
                                }
                            }
                        val imported = manager.importBytes(bytes)
                        NewsNotificationWorker.syncSchedule(
                            context,
                            imported.notificationEnabled,
                        )
                        KanarekWidgetProvider.refreshAll(context)
                        PlayerWidgetProvider.updateAll(
                            context = context,
                            station = imported.currentStation,
                            isPlaying = false,
                        )
                        context.getString(
                            R.string.backup_imported,
                            imported.feedCount,
                            imported.stationCount,
                            imported.savedArticleCount,
                        )
                    } catch (error: Exception) {
                        context.getString(backupErrorMessage(error))
                    } finally {
                        setBusy(false)
                    }
            }
        }

    Card(modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.backup_and_restore),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                text = stringResource(R.string.backup_summary),
                style = MaterialTheme.typography.bodyMedium,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(
                    onClick = { exportLauncher.launch("kanarek-backup.xml") },
                    enabled = enabled && !busy,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(stringResource(R.string.backup_export))
                }
                OutlinedButton(
                    onClick = {
                        importLauncher.launch(
                            arrayOf("application/xml", "text/xml", "*/*"),
                        )
                    },
                    enabled = enabled && !busy,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(stringResource(R.string.backup_import))
                }
            }
            if (busy) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                ) {
                    CircularProgressIndicator()
                }
            }
            status?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

private fun backupErrorMessage(error: Exception): Int =
    when {
        error is BackupTooLargeException ||
            (error is IOException && error.message?.contains("exceeds") == true) ->
            R.string.backup_import_too_large
        error is BackupFormatException -> R.string.backup_import_invalid
        else -> R.string.backup_import_failed
    }
