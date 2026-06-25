package com.feedy.widget

import android.app.Activity
import android.content.Intent
import android.os.Bundle

/**
 * Tiny no-UI trampoline for widget card taps.
 *
 * The slideshow's collection click template must be a *mutable* PendingIntent (the
 * per-item fill-in intent supplies the article URL). On Android 14+ a mutable
 * PendingIntent wrapping an *implicit* intent is illegal and throws, so the template
 * targets this explicit activity instead; we read the filled-in URL from the intent
 * data and re-dispatch it as a normal ACTION_VIEW.
 */
class ArticleRedirectActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        intent?.data?.let { url ->
            runCatching {
                startActivity(
                    Intent(Intent.ACTION_VIEW, url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                )
            }
        }
        finish()
    }
}
