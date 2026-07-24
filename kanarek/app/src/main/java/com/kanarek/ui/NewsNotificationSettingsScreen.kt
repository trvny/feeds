package com.kanarek.ui

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.kanarek.R
import com.kanarek.data.NewsNotificationConfig
import java.util.Locale
import kotlin.math.roundToInt

@Composable
internal fun NewsNotificationSettingsScreen(
    config: NewsNotificationConfig,
    availableFeeds: List<String>,
    onSave: (NewsNotificationConfig) -> Unit,
    modifier: Modifier = Modifier,
) {
    val reconciledConfig =
        remember(config, availableFeeds) {
            config.reconciledWith(availableFeeds)
        }
    val feedOptions =
        remember(availableFeeds) {
            availableFeeds
                .map(String::trim)
                .filter(String::isNotEmpty)
                .distinct()
        }
    var enabled by remember(config) { mutableStateOf(config.enabled) }
    var selectedFeeds by
        remember(reconciledConfig, feedOptions) {
            mutableStateOf(reconciledConfig.selectedFeeds.toSet())
        }
    var quietEnabled by remember(config) { mutableStateOf(config.quietHoursEnabled) }
    var quietStartHour by remember(config) { mutableIntStateOf(config.quietStartMinute / 60) }
    var quietEndHour by remember(config) { mutableIntStateOf(config.quietEndMinute / 60) }

    NotificationSettingsContent(
        state =
            NotificationSettingsUiState(
                enabled = enabled,
                feedOptions = feedOptions,
                selectedFeeds = selectedFeeds,
                quietEnabled = quietEnabled,
                quietStartHour = quietStartHour,
                quietEndHour = quietEndHour,
            ),
        actions =
            NotificationSettingsActions(
                onEnabledChange = { enabled = it },
                onSelectedFeedsChange = { selectedFeeds = it },
                onQuietEnabledChange = { quietEnabled = it },
                onQuietStartHourChange = { quietStartHour = it },
                onQuietEndHourChange = { quietEndHour = it },
                onSave = {
                    onSave(
                        NewsNotificationConfig(
                            enabled = enabled,
                            selectedFeeds = selectedFeeds.toList(),
                            configuredFeeds = feedOptions,
                            quietHoursEnabled = quietEnabled,
                            quietStartMinute = quietStartHour * 60,
                            quietEndMinute = quietEndHour * 60,
                        ),
                    )
                },
            ),
        modifier = modifier,
    )
}

private data class NotificationSettingsUiState(
    val enabled: Boolean,
    val feedOptions: List<String>,
    val selectedFeeds: Set<String>,
    val quietEnabled: Boolean,
    val quietStartHour: Int,
    val quietEndHour: Int,
)

private data class NotificationSettingsActions(
    val onEnabledChange: (Boolean) -> Unit,
    val onSelectedFeedsChange: (Set<String>) -> Unit,
    val onQuietEnabledChange: (Boolean) -> Unit,
    val onQuietStartHourChange: (Int) -> Unit,
    val onQuietEndHourChange: (Int) -> Unit,
    val onSave: () -> Unit,
)

@Composable
private fun NotificationSettingsContent(
    state: NotificationSettingsUiState,
    actions: NotificationSettingsActions,
    modifier: Modifier,
) {
    Column(
        modifier =
            modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        NotificationMasterToggle(state.enabled, actions.onEnabledChange)
        if (state.enabled) {
            NotificationSources(
                feeds = state.feedOptions,
                selectedFeeds = state.selectedFeeds,
                onSelectedFeedsChange = actions.onSelectedFeedsChange,
            )
            NotificationInterval()
            QuietHoursSettings(
                state = state,
                actions = actions,
            )
            Text(
                stringResource(R.string.news_notification_permission_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        NotificationSaveButton(
            enabled = state.enabled,
            hasSelectedFeeds = state.selectedFeeds.isNotEmpty(),
            onSave = actions.onSave,
        )
    }
}

@Composable
private fun NotificationMasterToggle(
    enabled: Boolean,
    onEnabledChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Switch(checked = enabled, onCheckedChange = onEnabledChange)
        Column {
            Text(
                stringResource(R.string.news_notifications_enabled),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                stringResource(R.string.news_notifications_enabled_summary),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun NotificationSources(
    feeds: List<String>,
    selectedFeeds: Set<String>,
    onSelectedFeedsChange: (Set<String>) -> Unit,
) {
    Text(
        stringResource(R.string.news_notification_sources),
        style = MaterialTheme.typography.labelLarge,
    )
    Text(
        stringResource(R.string.news_notification_sources_summary),
        style = MaterialTheme.typography.bodySmall,
    )
    feeds.forEach { feed ->
        val checked = feed in selectedFeeds
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clickable {
                        onSelectedFeedsChange(
                            if (checked) selectedFeeds - feed else selectedFeeds + feed,
                        )
                    }.padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Checkbox(checked = checked, onCheckedChange = null)
            Column {
                Text(feedLabel(feed), style = MaterialTheme.typography.bodyMedium)
                Text(
                    feed,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun NotificationInterval() {
    Text(
        stringResource(R.string.news_notification_interval),
        style = MaterialTheme.typography.labelLarge,
    )
    Text(
        stringResource(R.string.news_notification_interval_hourly),
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun QuietHoursSettings(
    state: NotificationSettingsUiState,
    actions: NotificationSettingsActions,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Switch(
            checked = state.quietEnabled,
            onCheckedChange = actions.onQuietEnabledChange,
        )
        Column {
            Text(
                stringResource(R.string.news_notification_quiet_hours),
                style = MaterialTheme.typography.titleSmall,
            )
            Text(
                stringResource(R.string.news_notification_quiet_hours_summary),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
    if (state.quietEnabled) {
        HourSlider(
            label = stringResource(R.string.news_notification_quiet_start),
            hour = state.quietStartHour,
            onHourChange = actions.onQuietStartHourChange,
        )
        HourSlider(
            label = stringResource(R.string.news_notification_quiet_end),
            hour = state.quietEndHour,
            onHourChange = actions.onQuietEndHourChange,
        )
    }
}

@Composable
private fun NotificationSaveButton(
    enabled: Boolean,
    hasSelectedFeeds: Boolean,
    onSave: () -> Unit,
) {
    val context = LocalContext.current
    val permissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    Button(
        enabled = !enabled || hasSelectedFeeds,
        onClick = {
            if (enabled &&
                Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.POST_NOTIFICATIONS,
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
            onSave()
        },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(stringResource(R.string.news_notification_save))
    }
}

@Composable
private fun HourSlider(
    label: String,
    hour: Int,
    onHourChange: (Int) -> Unit,
) {
    Column {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(label, style = MaterialTheme.typography.labelLarge)
            Text(formatHour(hour), style = MaterialTheme.typography.labelLarge)
        }
        Slider(
            value = hour.toFloat(),
            onValueChange = { onHourChange(it.roundToInt().coerceIn(0, 23)) },
            valueRange = 0f..23f,
            steps = 22,
        )
    }
}

private fun feedLabel(feed: String): String =
    Uri
        .parse(feed)
        .host
        ?.removePrefix("www.")
        ?.takeIf(String::isNotBlank)
        ?: feed

private fun formatHour(hour: Int): String =
    String.format(Locale.getDefault(), "%02d:00", hour.coerceIn(0, 23))
