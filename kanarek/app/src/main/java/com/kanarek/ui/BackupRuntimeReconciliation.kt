package com.kanarek.ui

import com.kanarek.data.Station

internal data class ImportedRuntimeState(
    val readerRefreshMinutes: Int,
    val notificationsEnabled: Boolean,
    val currentStation: Station?,
)

internal fun reconcileImportedRuntime(
    state: ImportedRuntimeState,
    syncReader: (Int) -> Unit,
    syncNotifications: (Boolean) -> Unit,
    refreshNewsWidgets: () -> Unit,
    updatePlayerWidgets: (Station?) -> Unit,
) {
    syncReader(state.readerRefreshMinutes)
    syncNotifications(state.notificationsEnabled)
    refreshNewsWidgets()
    updatePlayerWidgets(state.currentStation)
}
