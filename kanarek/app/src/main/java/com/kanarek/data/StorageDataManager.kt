package com.kanarek.data

import android.content.Context
import coil.imageLoader
import com.kanarek.widget.WidgetImageCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Performs cache file work away from the main thread. */
internal class StorageDataManager(
    context: Context,
) {
    private val appContext = context.applicationContext

    suspend fun usage(): StorageUsage =
        withContext(Dispatchers.IO) {
            val fileUsage =
                StorageFiles.usage(
                    feedCacheRoots = listOf(FeedCache.directory(appContext)),
                    imageCacheRoots = listOf(WidgetImageCache.directory(appContext)),
                )
            fileUsage.copy(
                imageCacheBytes =
                    fileUsage.imageCacheBytes +
                        (appContext.imageLoader.diskCache?.size ?: 0L),
            )
        }

    suspend fun clearFeedCache() {
        withContext(Dispatchers.IO) {
            StorageFiles.clearDirectory(FeedCache.directory(appContext))
        }
    }

    suspend fun clearImageCache() {
        withContext(Dispatchers.IO) {
            WidgetImageCache.clear(appContext)
            appContext.imageLoader.memoryCache?.clear()
            appContext.imageLoader.diskCache?.clear()
        }
    }
}
