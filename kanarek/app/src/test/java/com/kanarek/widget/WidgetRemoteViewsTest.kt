package com.kanarek.widget

import android.app.Application
import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.widget.FrameLayout
import android.widget.RemoteViews
import com.kanarek.R
import org.junit.Assert.assertNotEquals
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

    private fun inflate(
        layoutId: Int,
        context: Context = app,
    ): FrameLayout {
        val host = FrameLayout(context)
        RemoteViews(context.packageName, layoutId).apply(context, host)
        return host
    }

    private fun widgetContext(nightMode: Int): Context {
        val configuration = Configuration(app.resources.configuration)
        configuration.uiMode =
            (configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK.inv()) or nightMode
        return app.createConfigurationContext(configuration)
    }

    @Test
    fun `every widget layout inflates as RemoteViews in day and night modes`() {
        val contexts =
            listOf(
                widgetContext(Configuration.UI_MODE_NIGHT_NO),
                widgetContext(Configuration.UI_MODE_NIGHT_YES),
            )
        listOf(
            R.layout.widget,
            R.layout.widget_item,
            R.layout.widget_loading,
            R.layout.player_widget,
        ).forEach { layout ->
            val name = app.resources.getResourceEntryName(layout)
            contexts.forEach { context ->
                assertNotNull(
                    name,
                    runCatching { inflate(layout, context) }
                        .getOrElse { throw AssertionError(name, it) },
                )
            }
        }
    }

    @Test
    fun `widget surface is translucent and changes with night mode`() {
        val day =
            widgetContext(Configuration.UI_MODE_NIGHT_NO)
                .getColor(R.color.widget_surface)
        val night =
            widgetContext(Configuration.UI_MODE_NIGHT_YES)
                .getColor(R.color.widget_surface)

        assertNotEquals(day, night)
        assertTrue(Color.alpha(day) < 255)
        assertTrue(Color.alpha(night) < 255)
    }

    @Test
    fun `news widget builds in every status`() {
        val config =
            NewsWidgetConfig(
                feeds = listOf("https://example.com/feed.xml"),
                headlines = false,
                intervalSeconds = 7,
            )
        val provider = KanarekWidgetProvider()
        // Built, not inflated: the tree carries a setRemoteAdapter action that binds a real
        // RemoteViewsService, which has no meaning outside a launcher. The bare layout is
        // inflation-checked by the test above; here we only prove the build path never throws.
        // null => LOADING, non-null => READY; both format a different status string.
        listOf(null, 1_700_000_000_000L).forEach { updatedAt ->
            assertNotNull(
                provider.buildViews(
                    context = app,
                    appWidgetId = APP_WIDGET_ID,
                    config = config,
                    lastUpdatedMillis = updatedAt,
                ),
            )
        }
    }

    @Test
    fun `player widget builds and inflates in every state`() {
        listOf(
            PlayerWidgetState(station = null, isPlaying = false, errorText = null),
            PlayerWidgetState(station = null, isPlaying = true, errorText = null),
            PlayerWidgetState(station = null, isPlaying = false, errorText = "boom"),
        ).forEach { state ->
            val views = PlayerWidgetProvider.buildViews(app, APP_WIDGET_ID, state)
            assertNotNull(views.apply(app, FrameLayout(app)))
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
