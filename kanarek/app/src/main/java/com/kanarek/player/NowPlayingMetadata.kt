package com.kanarek.player

import com.kanarek.data.Station

internal fun streamMetadataText(
    station: Station?,
    title: CharSequence?,
    artist: CharSequence?,
): String? {
    val normalizedTitle = title.normalizedMetadata()
    val normalizedArtist = artist.normalizedMetadata()
    val dynamicTitle =
        normalizedTitle?.takeUnless { value ->
            value.equals(station?.name, ignoreCase = true)
        }
    val dynamicArtist =
        normalizedArtist?.takeUnless { value ->
            value.equals(station?.groupTitle, ignoreCase = true) ||
                value.equals(station?.name, ignoreCase = true)
        }
    return listOfNotNull(dynamicArtist, dynamicTitle)
        .distinctBy(String::lowercase)
        .joinToString(" — ")
        .takeIf(String::isNotBlank)
}

private fun CharSequence?.normalizedMetadata(): String? =
    this
        ?.toString()
        ?.trim()
        ?.takeIf(String::isNotEmpty)
