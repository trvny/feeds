package com.kanarek.data

/**
 * Container codec for multiple named playlists — pure Kotlin, no Android deps (mirrors [Opml]
 * and [M3uCodec]). The container is plain text: `#KANAREK-PLAYLIST:<name>` section markers, each
 * followed by that playlist's ordinary M3U text. Round-trips through [M3uCodec] per section, so
 * a single playlist extracted from the container is a valid standalone M3U file and vice versa.
 * Tolerant of malformed input — unnamed leading content is ignored, duplicate names keep the
 * last occurrence (later writes win).
 */
object Playlists {

    data class Named(val name: String, val stations: List<Station>)

    private const val MARKER = "#KANAREK-PLAYLIST:"

    /** Parse a container into named playlists, in file order. */
    fun parse(text: String): List<Named> {
        val sections = LinkedHashMap<String, StringBuilder>()
        var current: StringBuilder? = null
        text.lineSequence().forEach { line ->
            if (line.startsWith(MARKER)) {
                val name = line.removePrefix(MARKER).trim()
                if (name.isNotEmpty()) {
                    current = StringBuilder().also { sections[name] = it }
                } else {
                    current = null
                }
            } else {
                current?.append(line)?.append('\n')
            }
        }
        return sections.map { (name, body) -> Named(name, M3uCodec.parse(body.toString())) }
    }

    /** Serialize named playlists to the container format. */
    fun build(playlists: List<Named>): String = buildString {
        playlists.forEach { p ->
            append(MARKER).append(p.name.trim().replace("\n", " ")).append('\n')
            append(M3uCodec.build(p.stations))
        }
    }
}
