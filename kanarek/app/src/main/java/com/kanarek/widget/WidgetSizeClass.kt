package com.kanarek.widget

import android.appwidget.AppWidgetManager
import android.os.Bundle
import com.kanarek.R

internal enum class WidgetSizeClass { COMPACT, REGULAR, EXPANDED }

internal fun widgetSizeClass(options: Bundle): WidgetSizeClass =
    widgetSizeClass(
        widthDp = options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, DEFAULT_WIDGET_WIDTH_DP),
        heightDp = options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, DEFAULT_WIDGET_HEIGHT_DP),
    )

internal fun widgetSizeClass(
    widthDp: Int,
    heightDp: Int,
): WidgetSizeClass =
    when {
        widthDp < COMPACT_WIDTH_DP || heightDp < COMPACT_HEIGHT_DP -> WidgetSizeClass.COMPACT
        widthDp >= EXPANDED_WIDTH_DP && heightDp >= EXPANDED_HEIGHT_DP -> WidgetSizeClass.EXPANDED
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

private const val DEFAULT_WIDGET_WIDTH_DP = 240
private const val DEFAULT_WIDGET_HEIGHT_DP = 110
private const val COMPACT_WIDTH_DP = 200
private const val COMPACT_HEIGHT_DP = 90
private const val EXPANDED_WIDTH_DP = 300
private const val EXPANDED_HEIGHT_DP = 150
