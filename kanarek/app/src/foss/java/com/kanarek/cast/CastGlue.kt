package com.kanarek.cast

import android.content.Context
import androidx.media3.common.Player

/** FOSS twin of the play flavor's CastGlue: same surface, no Google Play services, no cast. */
object CastGlue {
    const val AVAILABLE: Boolean = false

    fun createCastPlayer(
        context: Context,
        onAvailability: (Player?) -> Unit,
    ): Player? = null

    fun releaseCastPlayer(player: Player?) = Unit
}
