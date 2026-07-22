package com.kanarek.player

import android.content.Context
import android.content.Intent
import android.util.Base64
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Authenticates the small set of custom startService actions used by Kanarek's private widget
 * receiver. PlayerService remains exported for Media3 controllers, but another app cannot forge
 * TOGGLE/NEXT/PREV by starting the service directly without this app-private random token.
 */
internal object PlayerActionAuth {
    private const val PREFS = "player_action_auth"
    private const val KEY_TOKEN = "token"
    private const val EXTRA_TOKEN = "com.kanarek.extra.PLAYER_ACTION_TOKEN"

    fun attach(
        context: Context,
        intent: Intent,
    ): Intent = intent.putExtra(EXTRA_TOKEN, token(context))

    fun accepts(
        context: Context,
        intent: Intent?,
    ): Boolean {
        val supplied = intent?.getStringExtra(EXTRA_TOKEN)?.toByteArray() ?: return false
        val expected = token(context).toByteArray()
        return MessageDigest.isEqual(supplied, expected)
    }

    private fun token(context: Context): String =
        synchronized(this) {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            prefs.getString(KEY_TOKEN, null)
                ?: ByteArray(32)
                    .also(SecureRandom()::nextBytes)
                    .let { Base64.encodeToString(it, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING) }
                    .also { prefs.edit().putString(KEY_TOKEN, it).apply() }
        }
}
