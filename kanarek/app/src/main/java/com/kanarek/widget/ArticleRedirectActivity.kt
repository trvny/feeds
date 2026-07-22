package com.kanarek.widget

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import com.kanarek.data.WebLinks

/**
 * Tiny no-UI trampoline for widget card taps.
 *
 * The slideshow's collection click template must be a *mutable* PendingIntent (the
 * per-item fill-in intent supplies the article URL). On Android 14+ a mutable
 * PendingIntent wrapping an *implicit* intent is illegal and throws, so the template
 * targets this explicit activity instead; we validate the filled-in URL and re-dispatch
 * only ordinary HTTP(S) article links as ACTION_VIEW.
 */
class ArticleRedirectActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        intent?.data?.let { url ->
            if (WebLinks.isHttpOrHttps(url.toString())) {
                runCatching {
                    startActivity(
                        Intent(Intent.ACTION_VIEW, url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                }
            }
        }
        finish()
    }
}
