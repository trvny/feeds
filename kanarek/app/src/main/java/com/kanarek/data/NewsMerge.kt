package com.kanarek.data

/**
 * Pure merge helpers for the combined news list. No Android deps, so it's
 * JVM-unit-tested directly (see NewsMergeTest).
 */
object NewsMerge {
    /**
     * Keep at most [cap] items per source (case-insensitive), so one high-volume
     * feed (a news wire, a chatty status feed) can't crowd everything else out of a
     * recency-sorted merge. Items with a blank source are never capped — each is
     * treated as its own source. The result is sorted newest-first; a [cap] of 0
     * (or less) returns the input sorted but otherwise untouched.
     */
    fun capPerSource(items: List<NewsItem>, cap: Int): List<NewsItem> {
        val sorted = items.sortedByDescending { it.publishedAtMillis ?: 0L }
        if (cap <= 0) return sorted
        val counts = HashMap<String, Int>()
        val out = ArrayList<NewsItem>(sorted.size)
        for (item in sorted) {
            val key = item.source.trim().lowercase()
            if (key.isEmpty()) {
                out.add(item)
                continue
            }
            val n = counts.getOrDefault(key, 0)
            if (n < cap) {
                counts[key] = n + 1
                out.add(item)
            }
        }
        return out
    }
}
