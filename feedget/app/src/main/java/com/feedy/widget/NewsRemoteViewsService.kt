package com.feedy.widget

import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.widget.RemoteViews
import android.widget.RemoteViewsService
import com.feedy.R
import com.feedy.data.NewsItem
import com.feedy.data.NewsRepository
import com.feedy.data.SettingsStore
import java.net.HttpURLConnection
import java.net.URL

/** Provides the collection of news cards the slideshow flips through. */
class NewsRemoteViewsService : RemoteViewsService() {
    override fun onGetViewFactory(intent: Intent): RemoteViewsFactory =
        NewsRemoteViewsFactory(applicationContext)
}

private class NewsRemoteViewsFactory(
    private val context: Context,
) : RemoteViewsService.RemoteViewsFactory {

    private val repository = NewsRepository()
    private val settings = SettingsStore(context)
    private var items: List<NewsItem> = emptyList()

    override fun onCreate() {}

    /** Runs on a background thread — network and disk are allowed here. */
    override fun onDataSetChanged() {
        val feeds = runCatching { settings.feedsBlocking() }.getOrDefault(NewsRepository.DEFAULT_FEEDS)
        val backend = runCatching { settings.backendUrlBlocking() }.getOrDefault("")
        items = runCatching { repository.fetchBlocking(feeds, backend, limit = ITEM_CAP) }.getOrDefault(emptyList())
    }

    override fun onDestroy() { items = emptyList() }

    override fun getCount(): Int = items.size
    override fun getViewTypeCount(): Int = 1
    override fun getItemId(position: Int): Long = items.getOrNull(position)?.link?.hashCode()?.toLong() ?: position.toLong()
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

            // Per-item click data merged into the provider's ACTION_VIEW template.
            val fillIn = Intent().apply { data = Uri.parse(item.link) }
            setOnClickFillInIntent(R.id.item_root, fillIn)
        }
    }

    /** Fetch + downscale an image so RemoteViews stays under the binder size limit. */
    private fun loadBitmap(url: String): Bitmap? = runCatching {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = IMG_TIMEOUT_MS
            readTimeout = IMG_TIMEOUT_MS
            instanceFollowRedirects = true
        }
        try {
            if (conn.responseCode !in 200..299) return null
            val bytes = conn.inputStream.use { it.readBytes() }
            decodeScaled(bytes, MAX_IMAGE_PX)
        } finally {
            conn.disconnect()
        }
    }.getOrNull()

    private fun decodeScaled(bytes: ByteArray, maxPx: Int): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        var sample = 1
        var w = bounds.outWidth
        var h = bounds.outHeight
        while (w / 2 >= maxPx || h / 2 >= maxPx) { w /= 2; h /= 2; sample *= 2 }
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
    }

    companion object {
        private const val ITEM_CAP = 12
        private const val MAX_IMAGE_PX = 400
        private const val IMG_TIMEOUT_MS = 6_000
    }
}
