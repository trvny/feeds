package com.kanarek

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Article
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Radio
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import com.kanarek.data.NewsNotificationStore
import com.kanarek.data.NewsRepository
import com.kanarek.data.SettingsStore
import com.kanarek.notifications.NewsNotificationWorker
import com.kanarek.ui.PlayerScreen
import com.kanarek.ui.ReaderScreen
import com.kanarek.ui.theme.KanarekTheme
import kotlinx.coroutines.launch

/**
 * The app's one window: the news reader and the radio/TV player live side by side as pages
 * of a [HorizontalPager] — swipe between them, tap the bottom navigation bar, or use the
 * navigation drawer (hamburger in either page's top bar), which also offers "close app".
 * Replaces the old three-activity setup (chooser -> MainActivity / PlayerActivity); the
 * player widget deep-links straight to the player page via [EXTRA_PAGE].
 */
class HomeActivity : ComponentActivity() {
    private val requestedPage = mutableIntStateOf(PAGE_READER)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        requestedPage.intValue = intent?.getIntExtra(EXTRA_PAGE, PAGE_READER) ?: PAGE_READER
        val settings = SettingsStore(applicationContext)
        val notifications = NewsNotificationStore(applicationContext)
        val repository = NewsRepository()
        lifecycleScope.launch {
            NewsNotificationWorker.syncSchedule(
                applicationContext,
                notifications.configNow().enabled,
            )
        }
        setContent {
            KanarekTheme {
                HomeShell(
                    settings = settings,
                    repository = repository,
                    requestedPage = requestedPage.intValue,
                    onCloseApp = { finishAffinity() },
                )
            }
        }
    }

    // singleTop: a player-widget tap while the app is already open lands here, not in onCreate.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        requestedPage.intValue = intent.getIntExtra(EXTRA_PAGE, requestedPage.intValue)
    }

    companion object {
        const val EXTRA_PAGE = "com.kanarek.extra.PAGE"
        const val PAGE_READER = 0
        const val PAGE_PLAYER = 1
    }
}

private const val PAGE_COUNT = 2

@Composable
private fun HomeShell(
    settings: SettingsStore,
    repository: NewsRepository,
    requestedPage: Int,
    onCloseApp: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val pagerState = rememberPagerState(initialPage = requestedPage) { PAGE_COUNT }

    // External page requests (widget deep-link via onNewIntent) steer the pager.
    LaunchedEffect(requestedPage) {
        if (pagerState.currentPage != requestedPage) pagerState.animateScrollToPage(requestedPage)
    }

    fun goTo(page: Int) {
        scope.launch {
            drawerState.close()
            pagerState.animateScrollToPage(page)
        }
    }
    val openMenu: () -> Unit = { scope.launch { drawerState.open() } }

    ModalNavigationDrawer(
        drawerState = drawerState,
        // Edge swipes belong to the pager; the drawer opens via the hamburger only
        // (and can still be swiped shut once open).
        gesturesEnabled = drawerState.isOpen,
        drawerContent = {
            ModalDrawerSheet {
                Text(
                    stringResource(R.string.app_name),
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.padding(horizontal = 28.dp, vertical = 20.dp),
                )
                NavigationDrawerItem(
                    icon = { Icon(Icons.Filled.Article, contentDescription = null) },
                    label = { Text(stringResource(R.string.home_news)) },
                    selected = pagerState.currentPage == HomeActivity.PAGE_READER,
                    onClick = { goTo(HomeActivity.PAGE_READER) },
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
                NavigationDrawerItem(
                    icon = { Icon(Icons.Filled.Radio, contentDescription = null) },
                    label = { Text(stringResource(R.string.player_title)) },
                    selected = pagerState.currentPage == HomeActivity.PAGE_PLAYER,
                    onClick = { goTo(HomeActivity.PAGE_PLAYER) },
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
                HorizontalDivider(Modifier.padding(vertical = 8.dp))
                NavigationDrawerItem(
                    icon = { Icon(Icons.Filled.Close, contentDescription = null) },
                    label = { Text(stringResource(R.string.close_app)) },
                    selected = false,
                    onClick = onCloseApp,
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
            }
        },
    ) {
        Scaffold(
            // The pages carry their own Scaffolds (their top bars handle the status bar) and
            // the NavigationBar below handles the system nav inset itself — so this outer
            // Scaffold must not add system-bar padding of its own.
            contentWindowInsets = WindowInsets(0.dp),
            bottomBar = {
                NavigationBar {
                    NavigationBarItem(
                        selected = pagerState.currentPage == HomeActivity.PAGE_READER,
                        onClick = { goTo(HomeActivity.PAGE_READER) },
                        icon = { Icon(Icons.Filled.Article, contentDescription = null) },
                        label = { Text(stringResource(R.string.home_news)) },
                    )
                    NavigationBarItem(
                        selected = pagerState.currentPage == HomeActivity.PAGE_PLAYER,
                        onClick = { goTo(HomeActivity.PAGE_PLAYER) },
                        icon = { Icon(Icons.Filled.Radio, contentDescription = null) },
                        label = { Text(stringResource(R.string.player_title)) },
                    )
                }
            },
        ) { padding ->
            HorizontalPager(
                state = pagerState,
                // Keep the neighbour page alive so the player's service binding (and the
                // reader's loaded stories) survive swiping away and back.
                beyondViewportPageCount = 1,
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(padding)
                        // The NavigationBar already covers the system nav area; stop the
                        // inner Scaffolds from padding their bottoms for it a second time.
                        .consumeWindowInsets(WindowInsets.navigationBars),
            ) { page ->
                when (page) {
                    HomeActivity.PAGE_READER ->
                        ReaderScreen(
                            settings = settings,
                            repository = repository,
                            isActive = pagerState.currentPage == HomeActivity.PAGE_READER,
                            onMenu = openMenu,
                        )
                    else -> PlayerScreen(settings = settings, onMenu = openMenu)
                }
            }
        }
    }
}
