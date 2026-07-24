package com.kanarek.data

import android.content.Context

internal class ReaderFeedStore(context: Context) {
    private val preferences =
        context.applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun snapshot(): ReaderFeedSnapshot? =
        synchronized(LOCK) {
            ReaderFeedSnapshotCodec.decode(preferences.getString(SNAPSHOT, null))
        }

    fun save(snapshot: ReaderFeedSnapshot) {
        synchronized(LOCK) {
            preferences
                .edit()
                .putString(SNAPSHOT, ReaderFeedSnapshotCodec.encode(snapshot))
                .commit()
        }
    }

    fun clear() {
        synchronized(LOCK) {
            preferences.edit().remove(SNAPSHOT).commit()
        }
    }

    companion object {
        private const val PREFERENCES_NAME = "reader_feed_cache"
        private const val SNAPSHOT = "snapshot"
        private val LOCK = Any()
    }
}
