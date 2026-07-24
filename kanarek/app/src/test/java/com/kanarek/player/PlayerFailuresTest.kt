package com.kanarek.player

import androidx.media3.common.PlaybackException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlayerFailuresTest {
    @Test
    fun classifiesNetworkHttpDecoderAndUnavailableErrors() {
        assertEquals(
            PlayerFailureKind.NETWORK,
            PlayerFailures.classify(PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED),
        )
        assertEquals(
            PlayerFailureKind.HTTP,
            PlayerFailures.classify(PlaybackException.ERROR_CODE_IO_BAD_HTTP_STATUS),
        )
        assertEquals(
            PlayerFailureKind.DECODER,
            PlayerFailures.classify(PlaybackException.ERROR_CODE_DECODING_FAILED),
        )
        assertEquals(
            PlayerFailureKind.UNAVAILABLE,
            PlayerFailures.classify(PlaybackException.ERROR_CODE_IO_FILE_NOT_FOUND),
        )
    }

    @Test
    fun transientNetworkErrorsUseBoundedExponentialBackoff() {
        val machine =
            PlayerFailureMachine(
                maxAutomaticRetries = 2,
                baseRetryDelayMs = 100L,
                maxRetryDelayMs = 1_000L,
            )

        val first = machine.onError(PlayerFailureKind.NETWORK)
        val second = machine.onError(PlayerFailureKind.NETWORK)
        val exhausted = machine.onError(PlayerFailureKind.NETWORK)

        assertEquals(100L, first.retryDelayMs)
        assertEquals(1, first.failure.automaticRetryAttempt)
        assertTrue(first.failure.retryPending)
        assertEquals(200L, second.retryDelayMs)
        assertEquals(2, second.failure.automaticRetryAttempt)
        assertTrue(second.failure.retryPending)
        assertNull(exhausted.retryDelayMs)
        assertEquals(2, exhausted.failure.automaticRetryAttempt)
        assertFalse(exhausted.failure.retryPending)
    }

    @Test
    fun permanentHttpAndDecoderErrorsWaitForManualRetry() {
        val machine = PlayerFailureMachine()

        val notFound = machine.onError(PlayerFailureKind.HTTP, httpStatus = 404)
        val decoder = machine.onError(PlayerFailureKind.DECODER)

        assertNull(notFound.retryDelayMs)
        assertNull(decoder.retryDelayMs)
        assertFalse(notFound.failure.retryPending)
        assertFalse(decoder.failure.retryPending)
    }

    @Test
    fun serverErrorsRetryButSuccessResetStartsFreshBudget() {
        val machine =
            PlayerFailureMachine(
                maxAutomaticRetries = 2,
                baseRetryDelayMs = 100L,
                maxRetryDelayMs = 1_000L,
            )

        val beforeReset = machine.onError(PlayerFailureKind.HTTP, httpStatus = 503)
        machine.reset()
        val afterReset = machine.onError(PlayerFailureKind.NETWORK)

        assertEquals(100L, beforeReset.retryDelayMs)
        assertEquals(1, beforeReset.failure.automaticRetryAttempt)
        assertEquals(100L, afterReset.retryDelayMs)
        assertEquals(1, afterReset.failure.automaticRetryAttempt)
    }
}
