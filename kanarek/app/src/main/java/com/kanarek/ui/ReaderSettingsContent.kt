package com.kanarek.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.kanarek.R

@Composable
internal fun ReaderSettingsContent(
    state: ReaderSettingsUiState,
    actions: ReaderSettingsActions,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier =
            modifier
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            stringResource(R.string.feeds_label),
            style = MaterialTheme.typography.labelLarge,
        )
        OutlinedTextField(
            value = state.feedText,
            onValueChange = actions.onFeedTextChange,
            modifier = Modifier.fillMaxWidth(),
            minLines = 3,
            maxLines = 6,
        )

        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedButton(onClick = actions.onImportOpml) {
                Text(stringResource(R.string.import_opml))
            }
            OutlinedButton(onClick = actions.onExportOpml) {
                Text(stringResource(R.string.export_opml))
            }
            OutlinedButton(onClick = actions.onAddSite) {
                Text(stringResource(R.string.add_site))
            }
        }

        Button(
            onClick = actions.onSave,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.save_update_widget))
        }

        OutlinedButton(
            onClick = actions.onOpenStorage,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.backup_storage_and_data))
        }
        OutlinedButton(
            onClick = actions.onOpenNotifications,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.news_notifications))
        }

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Switch(
                checked = state.headlinesMode,
                onCheckedChange = actions.onHeadlinesChange,
            )
            Text(
                stringResource(R.string.headlines_only),
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        Text(
            stringResource(R.string.per_source_cap),
            style = MaterialTheme.typography.labelLarge,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(0, 2, 3, 5).forEach { value ->
                FilterChip(
                    selected = state.perSourceCap == value,
                    onClick = { actions.onPerSourceCapChange(value) },
                    label = {
                        Text(
                            if (value == 0) {
                                stringResource(R.string.cap_off)
                            } else {
                                value.toString()
                            },
                        )
                    },
                )
            }
        }

        Text(
            stringResource(R.string.widget_hint),
            style = MaterialTheme.typography.bodySmall,
        )
        Text(
            stringResource(R.string.widget_interval),
            style = MaterialTheme.typography.labelLarge,
        )
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            listOf(5, 7, 10, 15, 30).forEach { seconds ->
                FilterChip(
                    selected = state.intervalSeconds == seconds,
                    onClick = { actions.onIntervalChange(seconds) },
                    label = {
                        Text(stringResource(R.string.widget_interval_seconds, seconds))
                    },
                )
            }
        }

        Spacer(Modifier.height(8.dp))
        Text(
            stringResource(R.string.reader_backend_optional),
            style = MaterialTheme.typography.labelLarge,
        )
        OutlinedTextField(
            value = state.backendText,
            onValueChange = actions.onBackendTextChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            placeholder = { Text(stringResource(R.string.backend_hint)) },
        )
        Spacer(Modifier.height(8.dp))
    }
}
