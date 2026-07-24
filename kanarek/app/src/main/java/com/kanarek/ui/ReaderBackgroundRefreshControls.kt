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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.kanarek.R
import com.kanarek.data.ReaderBackgroundRefresh

@Composable
internal fun ReaderBackgroundRefreshControls(
    selectedMinutes: Int,
    onSelected: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
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
