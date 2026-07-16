package com.kanarek.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Searches the community Radio Browser station directory (~50k internet radio stations) via the
 * kanarek Worker's `/stations/search` proxy (see `worker/src/index.ts`). The Worker picks a live
 * mirror and caches results, so the device never talks to Radio Browser directly. Results map
 * straight onto [Station] (`group` = first tag), so a search hit can be added to the station list
 * with no extra conversion step — same as any hand-added or imported station.
 *
 * Unlike [NewsRepository], there's no on-device fallback: the catalog only exists behind the
 * Worker, so this always goes through [NewsRepository.DEFAULT_BACKEND] unless a custom backend
 * URL is supplied.
 */
class StationDirectory {
    suspend fun search(
        query: String = "",
        country: String = "",
        tag: String = "",
        backendUrl: String = "",
        limit: Int = DEFAULT_LIMIT,
    ): List<Station> = withContext(Dispatchers.IO) { searchBlocking(query, country, tag, backendUrl, limit) }

    /** Blocking fetch — call off the main thread. */
    fun searchBlocking(
        query: String = "",
        country: String = "",
        tag: String = "",
        backendUrl: String = "",
        limit: Int = DEFAULT_LIMIT,
    ): List<Station> {
        val base = backendUrl.trim().trimEnd('/').ifBlank { NewsRepository.DEFAULT_BACKEND }
        val params =
            buildList {
                if (query.isNotBlank()) add("q=" + URLEncoder.encode(query.trim(), "UTF-8"))
                if (country.isNotBlank()) add("country=" + URLEncoder.encode(country.trim(), "UTF-8"))
                if (tag.isNotBlank()) add("tag=" + URLEncoder.encode(tag.trim(), "UTF-8"))
                add("limit=$limit")
            }
        if (params.size == 1) return emptyList() // only `limit` present -> no actual query terms
        val urlStr = "$base/stations/search?" + params.joinToString("&")

        val conn =
            (URL(urlStr).openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("Accept", "application/json")
            }
        try {
            if (conn.responseCode !in 200..299) error("HTTP ${conn.responseCode} for $urlStr")
            val body = conn.inputStream.bufferedReader().use(BufferedReader::readText)
            return parse(body)
        } finally {
            conn.disconnect()
        }
    }

    private fun parse(json: String): List<Station> {
        val arr = JSONObject(json).optJSONArray("stations") ?: return emptyList()
        return (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            val name = o.optString("name").takeIf { it.isNotBlank() } ?: return@mapNotNull null
            val streamUrl = o.optString("streamUrl").takeIf { it.isNotBlank() } ?: return@mapNotNull null
            Station(
                id = M3uCodec.idFor(streamUrl),
                name = name,
                streamUrl = streamUrl,
                logoUrl = o.optString("logoUrl").takeIf { it.isNotBlank() },
                groupTitle = o.optString("groupTitle").takeIf { it.isNotBlank() },
            )
        }
    }

    companion object {
        private const val TIMEOUT_MS = 8_000
        const val DEFAULT_LIMIT = 30
    }
}
