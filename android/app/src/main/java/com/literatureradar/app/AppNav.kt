package com.literatureradar.app

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.literatureradar.app.ui.about.AboutScreen
import com.literatureradar.app.ui.detail.PaperDetailScreen
import com.literatureradar.app.ui.feed.FeedScreen
import com.literatureradar.app.ui.saved.SavedScreen
import com.literatureradar.app.ui.search.SearchScreen
import com.literatureradar.app.ui.settings.SettingsScreen

private object Routes {
    const val Feed = "feed"
    const val Search = "search"
    const val Saved = "saved"
    const val Settings = "settings"
    const val About = "about"
    const val Paper = "paper/{id}"
    fun paper(id: Int) = "paper/$id"
}

@Composable
fun LiteratureAppRoot() {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val current = backStack?.destination?.route
    val showBottomBar = current == Routes.Feed ||
        current == Routes.Search ||
        current == Routes.Saved ||
        current == Routes.Settings

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    NavigationBarItem(
                        selected = current == Routes.Feed,
                        onClick = {
                            nav.navigate(Routes.Feed) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(Icons.Default.Home, contentDescription = null) },
                        label = { Text("推荐") },
                    )
                    NavigationBarItem(
                        selected = current == Routes.Search,
                        onClick = {
                            nav.navigate(Routes.Search) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(Icons.Default.Search, contentDescription = null) },
                        label = { Text("搜索") },
                    )
                    NavigationBarItem(
                        selected = current == Routes.Saved,
                        onClick = {
                            nav.navigate(Routes.Saved) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(Icons.Default.Star, contentDescription = null) },
                        label = { Text("收藏") },
                    )
                    NavigationBarItem(
                        selected = current == Routes.Settings,
                        onClick = {
                            nav.navigate(Routes.Settings) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                        label = { Text("设置") },
                    )
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = Routes.Feed,
            modifier = Modifier.padding(padding),
        ) {
            composable(Routes.Feed) {
                FeedScreen(onOpenPaper = { id -> nav.navigate(Routes.paper(id)) })
            }
            composable(Routes.Search) {
                SearchScreen(onOpenPaper = { id -> nav.navigate(Routes.paper(id)) })
            }
            composable(Routes.Saved) {
                SavedScreen(onOpenPaper = { id -> nav.navigate(Routes.paper(id)) })
            }
            composable(Routes.Settings) {
                SettingsScreen(onOpenAbout = { nav.navigate(Routes.About) })
            }
            composable(Routes.About) {
                AboutScreen(onBack = { nav.popBackStack() })
            }
            composable(
                Routes.Paper,
                arguments = listOf(navArgument("id") { type = NavType.IntType }),
            ) { entry ->
                val id = entry.arguments?.getInt("id") ?: return@composable
                PaperDetailScreen(paperId = id, onBack = { nav.popBackStack() })
            }
        }
    }
}
