package com.kanarek.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PlayerWakePolicyTest {
    @Test
    fun `radio never keeps the screen awake`() {
        assertFalse(
            shouldKeepPlayerScreenAwake(
                playbackActive = true,
                hasVideo = false,
                leaseActive = true,
            ),
        )
    }

    @Test
    fun `active TV playback keeps the screen awake during the lease`() {
        assertTrue(
            shouldKeepPlayerScreenAwake(
                playbackActive = true,
                hasVideo = true,
                leaseActive = true,
            ),
        )
    }

    @Test
    fun `paused TV and expired lease allow the screen to sleep`() {
        assertFalse(
            shouldKeepPlayerScreenAwake(
                playbackActive = false,
                hasVideo = true,
                leaseActive = true,
            ),
        )
        assertFalse(
            shouldKeepPlayerScreenAwake(
                playbackActive = true,
                hasVideo = true,
                leaseActive = false,
            ),
        )
    }
}
