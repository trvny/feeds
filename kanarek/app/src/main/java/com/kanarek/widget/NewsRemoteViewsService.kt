package com.kanarek.widget

import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.widget.RemoteViews
import android.widget.RemoteViewsService
import com.kanarek.R
import com.kanarek.data.FeedCache
import com.kanarek.data.Headlines
import com.kanarek.data.NewsItem
import com.kanarek.data.NewsRepository
import com.kanarek.data.SettingsStore
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

/** Provides the collection of news cards the slideshow flips through. */
class NewsRemoteViewsService : RemoteViewsService() {
    override fun onGetViewFactory(intent: Intent): RemoteViewsFactory = NewsRemoteViewsFactory(applicationContext)
}

private class NewsRemoteViewsFactory(
    private val context: Context,
) : RemoteViewsService.RemoteViewsFactory {
    private val repository = NewsRepository()
    private val settings = SettingsStore(context)
    private val feedCache = FeedCache(context)
    private var items: List<NewsItem> = emptyList()

    override fun onCreate() {}

    /** Runs on a background thread — network and disk are allowed here. */
    override fun onDataSetChanged() {
        val feeds = runCatching { settings.feedsBlocking() }.getOrDefault(NewsRepository.DEFAULT_FEEDS)
        val backend = runCatching { settings.backendUrlBlocking() }.getOrDefault("")
        val cap = runCatching { settings.perSourceCapBlocking() }.getOrDefault(0)
        val fetched =
            runCatching {
                repository.fetchBlocking(feeds, backend, limit = ITEM_CAP, cache = feedCache, perSourceCap = cap)
            }.getOrDefault(emptyList())
        // Keep the last good set on a transient failure rather than blanking to the empty view.
        val base =
            if (fetched.isNotEmpty()) {
                lastGood = fetched
                fetched
            } else {
                lastGood
            }
        // In headlines mode, narrow to the hottest stories; otherwise show everything.
        val headlines = runCatching { settings.headlinesModeBlocking() }.getOrDefault(false)
        items =
            if (headlines && base.isNotEmpty()) {
                val top = runCatching { settings.topSourcesBlocking() }.getOrDefault(emptySet())
                Headlines.headlines(base, topSources = top, limit = HEADLINES_CAP)
            } else {
                base
            }
    }

    override fun onDestroy() {
        items = emptyList()
    }

    override fun getCount(): Int = items.size

    override fun getViewTypeCount(): Int = 1

    override fun getItemId(position: Int): Long =
        items
            .getOrNull(position)
            ?.link
            ?.hashCode()
            ?.toLong() ?: position.toLong()

    override fun hasStableIds(): Boolean = true

    override fun getLoadingView(): RemoteViews? = null

    override fun getViewAt(position: Int): RemoteViews {
        val item = items.getOrNull(position) ?: return RemoteViews(context.packageName, R.layout.widget_item)
        return RemoteViews(context.packageName, R.layout.widget_item).apply {
            setTextViewText(R.id.item_title, item.title)
            setTextViewText(R.id.item_summary, item.summary)
            setTextViewText(R.id.item_source, item.source)

            val bitmap = item.imageUrl?.let { loadBitmap(it) }
            if (bitmap != null) {
                setImageViewBitmap(R.id.item_image, bitmap)
                setViewVisibility(R.id.item_image, android.view.View.VISIBLE)
                setViewVisibility(R.id.item_scrim, android.view.View.VISIBLE)
            } else {
                setViewVisibility(R.id.item_image, android.view.View.GONE)
                setViewVisibility(R.id.item_scrim, android.view.View.GONE)
            }

            // Source favicon (always, even when a full thumbnail is present) — pulled from a
            // CDN keyed on the article host, cached through the same two-tier bitmap cache.
            // Falls back to the bundled RSS glyph when the CDN has no icon. Always VISIBLE;
            // the resource is reset explicitly because RemoteViews recycles convert-views.
            val favicon = faviconUrl(item.link)?.let { loadBitmap(it) }
            if (favicon != null) {
                setImageViewBitmap(R.id.item_favicon, favicon)
            } else {
                setImageViewResource(R.id.item_favicon, R.drawable.ic_rss_fallback)
            }
            setViewVisibility(R.id.item_favicon, android.view.View.VISIBLE)

            // Per-item click data merged into the provider's ACTION_VIEW template.
            val fillIn = Intent().apply { data = Uri.parse(item.link) }
            setOnClickFillInIntent(R.id.item_root, fillIn)
        }
    }

    /** Favicon CDN URL for an article link's host, or null if the host can't be parsed. */
    private fun faviconUrl(link: String): String? {
        val host = runCatching { URI(link).host?.removePrefix("www.") }.getOrNull()
        return if (host.isNullOrBlank()) null else "https://icons.duckduckgo.com/ip3/$host.ico"
    }

    /** Cache-first fetch + downscale so RemoteViews stays under the binder size limit. */
    private fun loadBitmap(url: String): Bitmap? {
        WidgetImageCache.get(context, url)?.let { return it }
        return runCatching {
            val conn =
                (URL(url).openConnection() as HttpURLConnection).apply {
                    connectTimeout = IMG_TIMEOUT_MS
                    readTimeout = IMG_TIMEOUT_MS
                    instanceFollowRedirects = true
                }
            try {
                if (conn.responseCode !in 200..299) return null
                val bytes = conn.inputStream.use { it.readBytes() }
                decodeScaled(bytes, MAX_IMAGE_PX)?.also { WidgetImageCache.put(context, url, it) }
            } finally {
                conn.disconnect()
            }
        }.getOrNull()
    }

    private fun decodeScaled(
        bytes: ByteArray,
        maxPx: Int,
    ): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        var sample = 1
        var w = bounds.outWidth
        var h = bounds.outHeight
        while (w / 2 >= maxPx || h / 2 >= maxPx) {
            w /= 2
            h /= 2
            sample *= 2
        }
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
    }

    companion object {
        private const val ITEM_CAP = 12
        private const val HEADLINES_CAP = 6
        private const val MAX_IMAGE_PX = 400
        private const val IMG_TIMEOUT_MS = 6_000

        /** Process-wide last-known-good items, so a transient refresh failure can't blank the widget. */
        @Volatile private var lastGood: List<NewsItem> = emptyList()
    }
}
