package com.kanarek.cast

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cast
import androidx.compose.material.icons.filled.CastConnected
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.mediarouter.media.MediaRouteSelector
import androidx.mediarouter.media.MediaRouter
import com.google.android.gms.cast.CastMediaControlIntent
import com.kanarek.R

/**
 * Cast button + a plain-Compose device picker over [MediaRouter]. Deliberately NOT the framework
 * `MediaRouteButton`: that one requires a FragmentActivity host and an AppCompat theme for its
 * chooser dialog — kanarek is a plain ComponentActivity on a platform Material theme, so the
 * stock button would crash on tap. Selecting a cast route here is all the Cast framework needs
 * to start a session (CastContext listens to MediaRouter selection); PlayerService then hears
 * about it via CastGlue's SessionAvailabilityListener and hands playback over.
 *
 * The foss flavor's twin of this composable renders nothing.
 */
@Composable
fun CastButton(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val router = remember { MediaRouter.getInstance(context) }
    val selector =
        remember {
            MediaRouteSelector
                .Builder()
                .addControlCategory(
                    CastMediaControlIntent.categoryForCast(
                        CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID,
                    ),
                ).build()
        }
    var showPicker by remember { mutableStateOf(false) }
    var routes by remember { mutableStateOf(listOf<MediaRouter.RouteInfo>()) }
    var connected by remember { mutableStateOf(false) }

    fun refresh() {
        routes = router.routes.filter { !it.isDefault && it.matchesSelector(selector) }
        connected = router.selectedRoute.matchesSelector(selector)
    }

    // Passive discovery while merely showing the icon (cheap, keeps `connected` honest);
    // active scan only while the picker dialog is open — active scanning drains battery.
    DisposableEffect(showPicker) {
        val callback =
            object : MediaRouter.Callback() {
                override fun onRouteAdded(
                    router: MediaRouter,
                    route: MediaRouter.RouteInfo,
                ) = refresh()

                override fun onRouteRemoved(
                    router: MediaRouter,
                    route: MediaRouter.RouteInfo,
                ) = refresh()

                override fun onRouteChanged(
                    router: MediaRouter,
                    route: MediaRouter.RouteInfo,
                ) = refresh()

                override fun onRouteSelected(
                    router: MediaRouter,
                    route: MediaRouter.RouteInfo,
                    reason: Int,
                ) = refresh()

                override fun onRouteUnselected(
                    router: MediaRouter,
                    route: MediaRouter.RouteInfo,
                    reason: Int,
                ) = refresh()
            }
        router.addCallback(
            selector,
            callback,
            if (showPicker) MediaRouter.CALLBACK_FLAG_ACTIVE_SCAN else 0,
        )
        refresh()
        onDispose { router.removeCallback(callback) }
    }

    IconButton(onClick = { showPicker = true }, modifier = modifier) {
        Icon(
            imageVector = if (connected) Icons.Filled.CastConnected else Icons.Filled.Cast,
            contentDescription = stringResource(R.string.cast),
            tint = if (connected) MaterialTheme.colorScheme.primary else androidx.compose.ui.graphics.Color.Unspecified,
        )
    }

    if (showPicker) {
        AlertDialog(
            onDismissRequest = { showPicker = false },
            title = { Text(stringResource(R.string.cast_devices)) },
            text = {
                Column {
                    if (routes.isEmpty()) {
                        Text(stringResource(R.string.cast_no_devices))
                    } else {
                        routes.forEach { route ->
                            val isSelected = route.isSelected
                            Text(
                                text = route.name + if (isSelected) "  ✓" else "",
                                style = MaterialTheme.typography.bodyLarge,
                                color =
                                    if (isSelected) {
                                        MaterialTheme.colorScheme.primary
                                    } else {
                                        MaterialTheme.colorScheme.onSurface
                                    },
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .clickable {
                                            router.selectRoute(route)
                                            showPicker = false
                                        }.padding(vertical = 12.dp),
                            )
                        }
                    }
                }
            },
            confirmButton = {
                if (connected) {
                    TextButton(
                        onClick = {
                            router.unselect(MediaRouter.UNSELECT_REASON_DISCONNECTED)
                            showPicker = false
                        },
                    ) { Text(stringResource(R.string.cast_disconnect)) }
                }
            },
            dismissButton = {
                TextButton(onClick = { showPicker = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            },
        )
    }
}
