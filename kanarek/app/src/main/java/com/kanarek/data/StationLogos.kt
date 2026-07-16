package com.kanarek.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Resolves channel logos from the iptv-org catalog via the kanarek Worker's `/logos` proxy (see
 * `worker/src/index.ts`). The join key is [Station.tvgId] (the M3U `tvg-id`, which is the iptv-org
 * channel id). The Worker fetches the ~7 MB `logos.json` once, reduces it to a compact
 * `{ channelId: url }` map, and serves slices — so the device only ever sends a short id list and
 * gets back a small map, never the whole catalog.
 *
 * Like [StationDirectory], the catalog only exists behind the Worker: there's no on-device
 * fallback, and calls go through [NewsRepository.DEFAULT_BACKEND] unless a custom backend is set.
 * Every method is best-effort — a network failure yields an empty map (or the input list
 * unchanged), never an exception, so enrichment can never block or break an import.
 */
class StationLogos {
    /** Fetch `{ tvgId -> logoUrl }` for the given ids. Best-effort: returns `{}` on any failure. */
    suspend fun resolve(
        tvgIds: Collection<String>,
        backendUrl: String = "",
    ): Map<String, String> = withContext(Dispatchers.IO) { resolveBlocking(tvgIds, backendUrl) }

    /** Blocking fetch — call off the main thread. */
    fun resolveBlocking(
        tvgIds: Collection<String>,
        backendUrl: String = "",
    ): Map<String, String> {
        val ids = tvgIds.map { it.trim() }.filter { it.isNotEmpty() }.distinct().take(MAX_IDS)
        if (ids.isEmpty()) return emptyMap()

        val base = backendUrl.trim().trimEnd('/').ifBlank { NewsRepository.DEFAULT_BACKEND }
        val encoded = ids.joinToString(",") { URLEncoder.encode(it, "UTF-8") }
        val urlStr = "$base/logos?ids=$encoded"

        return runCatching {
            val conn =
                (URL(urlStr).openConnection() as HttpURLConnection).apply {
                    connectTimeout = TIMEOUT_MS
                    readTimeout = TIMEOUT_MS
                    instanceFollowRedirects = true
                    setRequestProperty("Accept", "application/json")
                }
            try {
                if (conn.responseCode !in 200..299) return emptyMap()
                val body = conn.inputStream.bufferedReader().use(BufferedReader::readText)
                parse(body)
            } finally {
                conn.disconnect()
            }
        }.getOrDefault(emptyMap())
    }

    /**
     * Fill [Station.logoUrl] for stations that carry a [Station.tvgId] but no logo yet, leaving
     * every other station (and any station that already has a logo) untouched. If nothing needs a
     * logo, or the lookup comes back empty, the original list is returned unchanged.
     */
    suspend fun enrich(
        stations: List<Station>,
        backendUrl: String = "",
    ): List<Station> {
        val needing = stations.filter { it.logoUrl.isNullOrBlank() && !it.tvgId.isNullOrBlank() }
        if (needing.isEmpty()) return stations
        val logos = resolve(needing.mapNotNull { it.tvgId }, backendUrl)
        if (logos.isEmpty()) return stations
        return stations.map { s ->
            if (s.logoUrl.isNullOrBlank()) {
                logos[s.tvgId]?.let { s.copy(logoUrl = it) } ?: s
            } else {
                s
            }
        }
    }

    private fun parse(body: String): Map<String, String> {
        val logos = JSONObject(body).optJSONObject("logos") ?: return emptyMap()
        val out = LinkedHashMap<String, String>()
        val keys = logos.keys()
        while (keys.hasNext()) {
            val k = keys.next()
            val v = logos.optString(k).takeIf { it.isNotBlank() } ?: continue
            out[k] = v
        }
        return out
    }

    companion object {
        private const val TIMEOUT_MS = 8_000
        private const val MAX_IDS = 200 // keep in step with the Worker's MAX_LOGO_IDS
    }
}
