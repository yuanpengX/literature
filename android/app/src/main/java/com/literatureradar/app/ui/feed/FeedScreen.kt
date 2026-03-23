package com.literatureradar.app.ui.feed

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.data.AnalyticsEventJson
import com.literatureradar.app.data.PaperJson
import com.literatureradar.app.data.toEntity
import com.literatureradar.app.data.toPaperJson
import com.literatureradar.app.ui.components.PaperCard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeedScreen(
    onOpenPaper: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val dao = ServiceLocator.db.paperDao()
    val analytics = ServiceLocator.analytics
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<PaperJson>>(emptyList()) }
    var nextCursor by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var loadingMore by remember { mutableStateOf(false) }
    var refreshing by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun applyImpressions(page: List<PaperJson>) {
        if (page.isEmpty()) return
        page.take(20).forEachIndexed { index, p ->
            analytics.log(
                AnalyticsEventJson(
                    eventType = "feed_impression",
                    paperId = p.id,
                    surface = "feed",
                    position = index,
                ),
            )
        }
    }

    suspend fun refreshFirstPage() {
        val res = ServiceLocator.api.getFeed(cursor = null, limit = 30, sort = "recommended")
        items = res.items
        nextCursor = res.nextCursor
        if (res.items.isNotEmpty()) {
            withContext(Dispatchers.IO) {
                dao.upsertAll(res.items.map { it.toEntity() })
            }
            applyImpressions(res.items)
        }
    }

    suspend fun loadMore() {
        val c = nextCursor ?: return
        loadingMore = true
        try {
            val res = ServiceLocator.api.getFeed(cursor = c, limit = 30, sort = "recommended")
            if (res.items.isEmpty()) {
                nextCursor = null
                return
            }
            items = items + res.items
            nextCursor = res.nextCursor
            withContext(Dispatchers.IO) {
                dao.upsertAll(res.items.map { it.toEntity() })
            }
        } finally {
            loadingMore = false
        }
    }

    LaunchedEffect(Unit) {
        loading = true
        error = null
        withContext(Dispatchers.IO) {
            val cached = dao.listRecent(80)
            if (cached.isNotEmpty()) {
                withContext(Dispatchers.Main) {
                    items = cached.map { it.toPaperJson() }
                    loading = false
                }
            }
        }
        runCatching { refreshFirstPage() }
            .onFailure { error = it.message ?: "加载失败" }
        loading = false
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("推荐", style = MaterialTheme.typography.titleLarge) },
            )
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = refreshing,
            onRefresh = {
                scope.launch {
                    refreshing = true
                    error = null
                    runCatching { refreshFirstPage() }
                        .onFailure { error = it.message }
                    refreshing = false
                }
            },
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when {
                loading && items.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                error != null && items.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(error!!, style = MaterialTheme.typography.bodyLarge)
                    }
                }
                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        itemsIndexed(items, key = { _, p -> p.id }) { index, paper ->
                            PaperCard(
                                paper = paper,
                                position = index,
                                onClick = {
                                    analytics.log(
                                        AnalyticsEventJson(
                                            eventType = "paper_open",
                                            paperId = paper.id,
                                            surface = "feed",
                                            position = index,
                                        ),
                                    )
                                    onOpenPaper(paper.id)
                                },
                            )
                        }
                        item {
                            if (nextCursor != null) {
                                Box(
                                    Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 8.dp),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    if (loadingMore) {
                                        CircularProgressIndicator()
                                    } else {
                                        TextButton(
                                            onClick = { scope.launch { loadMore() } },
                                            enabled = !loadingMore,
                                        ) {
                                            Text("加载更多")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
