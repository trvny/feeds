package com.feedy.data

/**
 * A single playable stream — an IPTV channel or an internet radio station. [id] is a stable
 * hash of [streamUrl] (see [M3uCodec]), so re-importing or re-parsing the same URL never mints
 * a new identity for it. [userAgent]/[referrer] are per-stream HTTP request headers some sources
 * require (geo/hotlink checks) — threaded into playback via [com.feedy.player.PlayerService].
 */
data class Station(
    val id: String,
    val name: String,
    val streamUrl: String,
    val logoUrl: String? = null,
    val groupTitle: String? = null,
    val userAgent: String? = null,
    val referrer: String? = null,
)
