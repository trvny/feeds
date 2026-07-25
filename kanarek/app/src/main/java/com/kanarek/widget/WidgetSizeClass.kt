package com.kanarek.widget

import android.appwidget.AppWidgetManager
import android.os.Bundle
import com.kanarek.R

internal enum class WidgetSizeClass { COMPACT, REGULAR, EXPANDED }

internal fun newsWidgetSizeClass(options: Bundle): WidgetSizeClass =
    newsWidgetSizeClass(
        widthDp = options.widgetWidthDp(),
        heightDp = options.widgetHeightDp(),
    )

internal fun playerWidgetSizeClass(options: Bundle): WidgetSizeClass =
    playerWidgetSizeClass(
        widthDp = options.widgetWidthDp(),
        heightDp = options.widgetHeightDp(),
    )

internal fun newsWidgetSizeClass(
    widthDp: Int,
    heightDp: Int,
): WidgetSizeClass =
    classifyWidgetSize(
        widthDp = widthDp,
        heightDp = heightDp,
        compactWidthDp = NEWS_COMPACT_WIDTH_DP,
        expandedHeightDp = NEWS_EXPANDED_HEIGHT_DP,
    )

internal fun playerWidgetSizeClass(
    widthDp: Int,
    heightDp: Int,
): WidgetSizeClass =
    classifyWidgetSize(
        widthDp = widthDp,
        heightDp = heightDp,
        compactWidthDp = PLAYER_COMPACT_WIDTH_DP,
        expandedHeightDp = PLAYER_EXPANDED_HEIGHT_DP,
    )

private fun classifyWidgetSize(
    widthDp: Int,
    heightDp: Int,
    compactWidthDp: Int,
    expandedHeightDp: Int,
): WidgetSizeClass =
    when {
        widthDp < compactWidthDp || heightDp < COMPACT_HEIGHT_DP -> WidgetSizeClass.COMPACT
        widthDp >= EXPANDED_WIDTH_DP && heightDp >= expandedHeightDp -> WidgetSizeClass.EXPANDED
        else -> WidgetSizeClass.REGULAR
    }

internal fun newsItemLayout(sizeClass: WidgetSizeClass): Int =
    when (sizeClass) {
        WidgetSizeClass.COMPACT -> R.layout.widget_item_compact
        WidgetSizeClass.REGULAR -> R.layout.widget_item
        WidgetSizeClass.EXPANDED -> R.layout.widget_item_expanded
    }

internal fun playerWidgetLayout(sizeClass: WidgetSizeClass): Int =
    when (sizeClass) {
        WidgetSizeClass.COMPACT -> R.layout.player_widget_compact
        WidgetSizeClass.REGULAR -> R.layout.player_widget
        WidgetSizeClass.EXPANDED -> R.layout.player_widget_expanded
    }

private fun Bundle.widgetWidthDp(): Int =
    getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, DEFAULT_WIDGET_WIDTH_DP)

private fun Bundle.widgetHeightDp(): Int =
    getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, DEFAULT_WIDGET_HEIGHT_DP)

private const val DEFAULT_WIDGET_WIDTH_DP = 240
private const val DEFAULT_WIDGET_HEIGHT_DP = 110
private const val NEWS_COMPACT_WIDTH_DP = 200
private const val PLAYER_COMPACT_WIDTH_DP = 260
private const val COMPACT_HEIGHT_DP = 90
private const val EXPANDED_WIDTH_DP = 300
private const val NEWS_EXPANDED_HEIGHT_DP = 220
private const val PLAYER_EXPANDED_HEIGHT_DP = 150
