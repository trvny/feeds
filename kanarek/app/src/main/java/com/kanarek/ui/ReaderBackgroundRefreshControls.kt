package com.kanarek.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kanarek.R
import com.kanarek.data.ReaderBackgroundRefresh
import com.kanarek.data.SettingsStore
import com.kanarek.widget.KanarekWidgetProvider
import kotlinx.coroutines.launch

@Composable
internal fun ReaderBackgroundRefreshControls(
    selectedMinutes: Int,
    onSelected: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val settings = remember(context) { SettingsStore(context.applicationContext) }
    val intervalSeconds by
        settings.intervalSeconds.collectAsStateWithLifecycle(
            initialValue = SettingsStore.DEFAULT_INTERVAL,
        )

    Column(
        modifier = modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Switch(
                checked = intervalSeconds != SettingsStore.INTERVAL_OFF,
                onCheckedChange = { enabled ->
                    scope.launch {
                        settings.setIntervalSeconds(
                            if (enabled) SettingsStore.DEFAULT_INTERVAL else SettingsStore.INTERVAL_OFF,
                        )
                        KanarekWidgetProvider.updateAll(context)
                    }
                },
            )
            Text(
                stringResource(R.string.widget_interval),
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        Text(
            stringResource(R.string.background_refresh),
            style = MaterialTheme.typography.labelLarge,
        )
        Text(
            stringResource(R.string.background_refresh_summary),
            style = MaterialTheme.typography.bodySmall,
        )
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ReaderBackgroundRefresh.options.forEach { minutes ->
                FilterChip(
                    selected = selectedMinutes == minutes,
                    onClick = { onSelected(minutes) },
                    label = {
                        Text(
                            when (minutes) {
                                ReaderBackgroundRefresh.OFF ->
                                    stringResource(R.string.background_refresh_off)
                                ReaderBackgroundRefresh.MINUTES_30 ->
                                    stringResource(R.string.background_refresh_minutes, minutes)
                                else ->
                                    stringResource(R.string.background_refresh_hours, minutes / 60)
                            },
                        )
                    },
                )
            }
        }
    }
}
