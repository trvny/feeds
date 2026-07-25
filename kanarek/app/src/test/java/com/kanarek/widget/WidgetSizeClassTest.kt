package com.kanarek.widget

import android.appwidget.AppWidgetManager
import android.content.res.Configuration
import android.os.Bundle
import com.kanarek.R
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class WidgetSizeClassTest {
    @Test
    fun `small width or height is compact`() {
        assertEquals(WidgetSizeClass.COMPACT, newsWidgetSizeClass(widthDp = 199, heightDp = 220))
        assertEquals(WidgetSizeClass.COMPACT, playerWidgetSizeClass(widthDp = 259, heightDp = 220))
        assertEquals(WidgetSizeClass.COMPACT, newsWidgetSizeClass(widthDp = 240, heightDp = 89))
    }

    @Test
    fun `middle sizes are regular`() {
        assertEquals(WidgetSizeClass.REGULAR, newsWidgetSizeClass(widthDp = 200, heightDp = 90))
        assertEquals(WidgetSizeClass.REGULAR, playerWidgetSizeClass(widthDp = 260, heightDp = 90))
        assertEquals(WidgetSizeClass.REGULAR, newsWidgetSizeClass(widthDp = 300, heightDp = 219))
        assertEquals(WidgetSizeClass.REGULAR, playerWidgetSizeClass(widthDp = 300, heightDp = 219))
    }

    @Test
    fun `large width and height are expanded`() {
        assertEquals(WidgetSizeClass.EXPANDED, newsWidgetSizeClass(widthDp = 300, heightDp = 220))
        assertEquals(WidgetSizeClass.EXPANDED, playerWidgetSizeClass(widthDp = 300, heightDp = 220))
    }

    @Test
    fun `launcher options pair dimensions for the current orientation`() {
        val options =
            Bundle().apply {
                putInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 340)
                putInt(AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 500)
                putInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 80)
                putInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 240)
            }

        assertEquals(
            WidgetSizeClass.EXPANDED,
            newsWidgetSizeClass(options, Configuration.ORIENTATION_PORTRAIT),
        )
        assertEquals(
            WidgetSizeClass.COMPACT,
            newsWidgetSizeClass(options, Configuration.ORIENTATION_LANDSCAPE),
        )
    }

    @Test
    fun `size classes map to dedicated layouts`() {
        assertEquals(R.layout.widget_item_compact, newsItemLayout(WidgetSizeClass.COMPACT))
        assertEquals(R.layout.widget_item, newsItemLayout(WidgetSizeClass.REGULAR))
        assertEquals(R.layout.widget_item_expanded, newsItemLayout(WidgetSizeClass.EXPANDED))
        assertEquals(R.layout.player_widget_compact, playerWidgetLayout(WidgetSizeClass.COMPACT))
        assertEquals(R.layout.player_widget, playerWidgetLayout(WidgetSizeClass.REGULAR))
        assertEquals(R.layout.player_widget_expanded, playerWidgetLayout(WidgetSizeClass.EXPANDED))
    }
}
