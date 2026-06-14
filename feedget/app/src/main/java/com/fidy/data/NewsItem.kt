package com.fidy.data

/** A single normalized news story shown in the slideshow. */
data class NewsItem(
    val title: String,
    val link: String,
    val summary: String,
    val imageUrl: String?,
    val source: String,
    val publishedAtMillis: Long?,
)
