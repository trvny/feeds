package com.kanarek.widget

import android.app.Application
import android.graphics.Color
import android.widget.FrameLayout
import android.widget.RemoteViews
import com.kanarek.R
import com.kanarek.data.Station
import com.kanarek.data.StationKind
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

/**
 * Guards the failure mode the launcher reports as "Can't add widget" / "Problem loading widget":
 * a RemoteViews tree that does not survive being built or inflated.
 *
 * Neither half is caught by anything else in the build. The compiler and lint see only the
 * builder calls, and an on-device smoke test of the *app* proves nothing, because the widget is
 * built in our process and inflated in the launcher's — `RemoteViews.apply` here is the same
 * call the launcher makes over there, and it rejects any view class not annotated `@RemoteView`,
 * any unresolvable resource, and any setter aimed at a missing id.
 *
 * Pinned to SDK 34 on purpose: the PendingIntent mutability rules these widgets depend on only
 * bite from API 31 up, so the test has to run well above the project's `minSdk` of 26.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class WidgetRemoteViewsTest {
    private val app: Application get() = RuntimeEnvironment.getApplication()

    private fun inflate(layoutId: Int): FrameLayout {
        val host = FrameLayout(app)
        RemoteViews(app.packageName, layoutId).apply(app, host)
        return host
    }

    private fun assertEveryWidgetLayoutInflates() {
        listOf(
            R.layout.widget,
            R.layout.widget_item_compact,
            R.layout.widget_item,
            R.layout.widget_item_expanded,
            R.layout.widget_loading,
            R.layout.player_widget_compact,
            R.layout.player_widget,
            R.layout.player_widget_expanded,
        ).forEach { layout ->
            val name = app.resources.getResourceEntryName(layout)
            assertNotNull(
                name,
                runCatching { inflate(layout) }.getOrElse { throw AssertionError(name, it) },
            )
        }
    }

    @Test
    fun `every widget layout inflates as RemoteViews`() {
        assertEveryWidgetLayoutInflates()
    }

    @Test
    @Config(sdk = [34], qualifiers = "night")
    fun `every widget layout inflates in night mode`() {
        assertEveryWidgetLayoutInflates()
    }

    @Test
    fun `widget surface is translucent`() {
        assertTrue(Color.alpha(app.getColor(R.color.widget_surface)) < 255)
    }

    @Test
    fun `news widget builds in every status and size`() {
        val config =
            NewsWidgetConfig(
                feeds = listOf("https://example.com/feed.xml"),
                headlines = false,
                intervalSeconds = 7,
            )
        val provider = KanarekWidgetProvider()
        WidgetSizeClass.entries.forEach { sizeClass ->
            listOf(null, 1_700_000_000_000L).forEach { updatedAt ->
                assertNotNull(
                    provider.buildViews(
                        context = app,
                        appWidgetId = APP_WIDGET_ID,
                        config = config,
                        lastUpdatedMillis = updatedAt,
                        sizeClass = sizeClass,
                    ),
                )
            }
        }
    }

    @Test
    fun `player widget builds and inflates in every state and size`() {
        val station =
            Station(
                id = "radio",
                name = "Radio Example",
                streamUrl = "https://example.com/live",
                groupTitle = "Music",
                kind = StationKind.RADIO,
            )
        val states =
            listOf(
                PlayerWidgetState(station = null, isPlaying = false),
                PlayerWidgetState(station = null, isPlaying = true),
                PlayerWidgetState(station = null, isPlaying = false, errorText = "boom"),
                PlayerWidgetState(
                    station = station,
                    isPlaying = true,
                    nowPlaying =
                        "Artist — A deliberately long track title for responsive rendering",
                ),
            )
        WidgetSizeClass.entries.forEach { sizeClass ->
            states.forEach { state ->
                val views =
                    PlayerWidgetProvider.buildViews(
                        context = app,
                        appWidgetId = APP_WIDGET_ID,
                        state = state,
                        sizeClass = sizeClass,
                    )
                assertNotNull(views.apply(app, FrameLayout(app)))
            }
        }
    }

    @Test
    fun `config activity cancels cleanly on an invalid widget id`() {
        val activity =
            Robolectric
                .buildActivity(NewsWidgetConfigActivity::class.java)
                .create()
                .get()
        assertTrue(activity.isFinishing)
    }

    private companion object {
        const val APP_WIDGET_ID = 42
    }
}
