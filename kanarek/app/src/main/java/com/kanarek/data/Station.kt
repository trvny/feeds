package com.kanarek.data

/** What kind of stream a [Station] is, so the UI can split TV from radio and only spend a
 *  video surface on the ones that carry a picture. [UNKNOWN] is the honest default for a
 *  hand-added station or an imported list that didn't say — it's treated as possibly-video. */
enum class StationKind { TV, RADIO, UNKNOWN }

/**
 * A single playable stream — an IPTV channel or an internet radio station. [id] is a stable
 * hash of [streamUrl] (see [M3uCodec]), so re-importing or re-parsing the same URL never mints
 * a new identity for it. [userAgent]/[referrer] are per-stream HTTP request headers some sources
 * require (geo/hotlink checks) — threaded into playback via [com.kanarek.player.PlayerService].
 */
data class Station(
    val id: String,
    val name: String,
    val streamUrl: String,
    val logoUrl: String? = null,
    val groupTitle: String? = null,
    /** iptv-org channel id (M3U `tvg-id`); the join key for logo/EPG enrichment. */
    val tvgId: String? = null,
    val userAgent: String? = null,
    val referrer: String? = null,
    /** TV vs radio, so the list can be filtered and only TV gets a video surface. Persisted as
     *  a `kanarek-kind` #EXTINF attribute by [M3uCodec]; defaults to [StationKind.UNKNOWN]. */
    val kind: StationKind = StationKind.UNKNOWN,
)
