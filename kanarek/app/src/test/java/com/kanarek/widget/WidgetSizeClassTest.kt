package com.kanarek.widget

import android.appwidget.AppWidgetManager
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
        assertEquals(WidgetSizeClass.COMPACT, widgetSizeClass(widthDp = 199, heightDp = 110))
        assertEquals(WidgetSizeClass.COMPACT, widgetSizeClass(widthDp = 240, heightDp = 89))
    }

    @Test
    fun `middle sizes are regular`() {
        assertEquals(WidgetSizeClass.REGULAR, widgetSizeClass(widthDp = 200, heightDp = 90))
        assertEquals(WidgetSizeClass.REGULAR, widgetSizeClass(widthDp = 300, heightDp = 149))
    }

    @Test
    fun `large width and height are expanded`() {
        assertEquals(WidgetSizeClass.EXPANDED, widgetSizeClass(widthDp = 300, heightDp = 150))
    }

    @Test
    fun `launcher options select the size class`() {
        val options =
            Bundle().apply {
                putInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 340)
                putInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 180)
            }
        assertEquals(WidgetSizeClass.EXPANDED, widgetSizeClass(options))
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
