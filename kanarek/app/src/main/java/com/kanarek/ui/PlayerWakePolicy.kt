package com.kanarek.ui

internal const val TV_WAKE_LEASE_MILLIS = 5L * 60L * 60L * 1_000L

internal fun shouldKeepPlayerScreenAwake(
    playbackActive: Boolean,
    hasVideo: Boolean,
    leaseActive: Boolean,
): Boolean = playbackActive && hasVideo && leaseActive
