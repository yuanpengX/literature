package com.literatureradar.app.ui.feed

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
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
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.util.NetworkErrorHumanizer
import com.literatureradar.app.data.AnalyticsEventJson
import com.literatureradar.app.data.PaperJson
import com.literatureradar.app.data.local.PaperEntity
import com.literatureradar.app.data.toEntity
import com.literatureradar.app.data.toPaperJson
import com.literatureradar.app.ui.components.PaperCard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** 与后端 `GET /feed?channel=` 一致 */
private enum class FeedChannel(val apiValue: String, val label: String) {
    Arxiv("arxiv", "arXiv"),
    Journal("journal", "期刊"),
    Conference("conference", "会议"),
}

/** 与后端 `GET /feed?sort=` 一致；Android 可用 X-User-Id，无小程序域名限制，保留双路排序 */
private enum class FeedSort(val apiValue: String, val label: String) {
    Hot("hot", "热门"),
    ForYou("for_you", "为你推荐"),
}

private fun PaperEntity.matchesChannel(ch: FeedChannel): Boolean = when (ch) {
    FeedChannel.Arxiv -> source == "arxiv"
    FeedChannel.Journal ->
        source == "openalex" ||
            source.startsWith("openalex:journal") ||
            source.startsWith("rss:")
    FeedChannel.Conference -> source.startsWith("openalex:conference")
}

/** 与 [load_candidate_papers] 频道规则一致；用于服务端未按 channel 过滤时的兜底（旧镜像 / 错误代理）。 */
private fun PaperJson.matchesChannel(ch: FeedChannel): Boolean = when (ch) {
    FeedChannel.Arxiv -> source == "arxiv"
    FeedChannel.Journal ->
        source == "openalex" ||
            source.startsWith("openalex:journal") ||
            source.startsWith("rss:")
    FeedChannel.Conference -> source.startsWith("openalex:conference")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeedScreen(
    onOpenPaper: (Int) -> Unit,
    /** 已在「推荐」Tab 时再次点「推荐」会递增，用于触发重新拉取第一页 */
    tabReselectSignal: Int = 0,
    modifier: Modifier = Modifier,
) {
    val dao = ServiceLocator.db.paperDao()
    val analytics = ServiceLocator.analytics
    val scope = rememberCoroutineScope()
    var selectedChannel by remember { mutableStateOf(FeedChannel.Arxiv) }
    var selectedSort by remember { mutableStateOf(FeedSort.ForYou) }
    var items by remember { mutableStateOf<List<PaperJson>>(emptyList()) }
    var nextCursor by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var loadingMore by remember { mutableStateOf(false) }
    var refreshing by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    /** 与 FeedResponse.blurbs_llm_ready 一致；未配置服务端 LLM 时为 false */
    var blurbsLlmReady by remember { mutableStateOf(false) }
    /** 服务端同步时间预算内未凑满一页，后台续跑 LLM；提示下拉刷新 */
    var blurbsGenerationIncomplete by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()
    var showBackTop by remember { mutableStateOf(false) }

    LaunchedEffect(listState) {
        snapshotFlow { listState.firstVisibleItemIndex }
            .distinctUntilChanged()
            .collect { idx -> showBackTop = idx > 3 }
    }

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
        val res = ServiceLocator.api.getFeed(
            cursor = null,
            limit = 30,
            sort = selectedSort.apiValue,
            channel = selectedChannel.apiValue,
        )
        blurbsLlmReady = res.blurbsLlmReady
        blurbsGenerationIncomplete = res.blurbsGenerationIncomplete
        items = res.items.filter { it.matchesChannel(selectedChannel) }
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
            val res = ServiceLocator.api.getFeed(
                cursor = c,
                limit = 30,
                sort = selectedSort.apiValue,
                channel = selectedChannel.apiValue,
            )
            blurbsLlmReady = blurbsLlmReady || res.blurbsLlmReady
            blurbsGenerationIncomplete = blurbsGenerationIncomplete || res.blurbsGenerationIncomplete
            if (res.items.isEmpty()) {
                nextCursor = res.nextCursor
                return
            }
            val page = res.items.filter { it.matchesChannel(selectedChannel) }
            items = items + page
            nextCursor = res.nextCursor
            withContext(Dispatchers.IO) {
                dao.upsertAll(res.items.map { it.toEntity() })
            }
        } finally {
            loadingMore = false
        }
    }

    LaunchedEffect(selectedChannel, selectedSort) {
        listState.scrollToItem(0, 0)
        error = null
        nextCursor = null
        blurbsLlmReady = false
        blurbsGenerationIncomplete = false
        withContext(Dispatchers.IO) {
            val cached = dao.listRecent(200).filter { it.matchesChannel(selectedChannel) }
            val withBlurbOnly = cached.map { it.toPaperJson() }.filter { it.feedBlurb.isNotBlank() }
            withContext(Dispatchers.Main) {
                // 勿展示无 feedBlurb 的 Room 缓存，避免「有卡片无中文摘要」
                items = withBlurbOnly
                loading = withBlurbOnly.isEmpty()
            }
        }
        runCatching { refreshFirstPage() }
            .onFailure { error = NetworkErrorHumanizer.message(it) }
        loading = false
    }

    LaunchedEffect(tabReselectSignal) {
        if (tabReselectSignal <= 0) return@LaunchedEffect
        refreshing = true
        error = null
        runCatching { ServiceLocator.api.requestSubscriptionFetch(selectedChannel.apiValue) }
        runCatching { refreshFirstPage() }
            .onFailure { error = NetworkErrorHumanizer.message(it) }
        refreshing = false
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("推荐", style = MaterialTheme.typography.titleLarge) },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surface),
            ) {
                TabRow(selectedTabIndex = selectedChannel.ordinal) {
                    FeedChannel.entries.forEach { ch ->
                        Tab(
                            selected = selectedChannel == ch,
                            onClick = { selectedChannel = ch },
                            text = { Text(ch.label) },
                        )
                    }
                }
                TabRow(selectedTabIndex = selectedSort.ordinal) {
                    FeedSort.entries.forEach { s ->
                        Tab(
                            selected = selectedSort == s,
                            onClick = { selectedSort = s },
                            text = { Text(s.label) },
                        )
                    }
                }
            }
            Box(
                Modifier
                    .weight(1f)
                    .fillMaxWidth(),
            ) {
                PullToRefreshBox(
                    isRefreshing = refreshing,
                    onRefresh = {
                        scope.launch {
                            refreshing = true
                            error = null
                            runCatching {
                                ServiceLocator.api.requestSubscriptionFetch(selectedChannel.apiValue)
                            }
                            runCatching { refreshFirstPage() }
                                .onFailure { error = NetworkErrorHumanizer.message(it) }
                            refreshing = false
                        }
                    },
                    modifier = Modifier.fillMaxSize(),
                ) {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                when {
                    loading && items.isEmpty() -> {
                        item(key = "loading") {
                            Box(
                                Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 420.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                CircularProgressIndicator()
                            }
                        }
                    }
                    error != null && items.isEmpty() -> {
                        item(key = "error") {
                            Box(
                                Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 420.dp)
                                    .padding(24.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(error!!, style = MaterialTheme.typography.bodyLarge)
                            }
                        }
                    }
                    !loading && items.isEmpty() -> {
                        item(key = "empty") {
                            Box(
                                Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 420.dp)
                                    .padding(24.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Column(
                                    verticalArrangement = Arrangement.spacedBy(12.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                ) {
                                    if (!blurbsLlmReady) {
                                        Text(
                                            "请先配置大模型",
                                            style = MaterialTheme.typography.titleMedium,
                                        )
                                        Text(
                                            "推荐列表只展示已生成「中文摘要（2～3 句）」的论文。请在「设置」中填写模型接口地址、API Key 与模型 ID，保存以同步到服务器，然后下拉刷新本页。",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    } else {
                                        Text(
                                            "暂无条目",
                                            style = MaterialTheme.typography.titleMedium,
                                        )
                                        Text(
                                            "当前频道下还没有带中文摘要的论文，或摘要仍在生成中。请稍后下拉刷新；也可在「订阅配置」中调整关键词、期刊与会议，再下拉触发抓取。",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                        if (selectedChannel == FeedChannel.Conference) {
                                            Text(
                                                "会议频道依赖 OpenAlex 会议 / proceedings 数据；可在订阅中添加会议 Source ID。",
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                    else -> {
                        if (blurbsGenerationIncomplete) {
                            item(key = "blurbs-incomplete-hint") {
                                Text(
                                    "摘要生成中，下拉刷新可加载更多",
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(bottom = 4.dp),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
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
                        item(key = "more") {
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
                if (showBackTop) {
                    FloatingActionButton(
                        onClick = {
                            scope.launch {
                                listState.animateScrollToItem(0)
                            }
                        },
                        modifier = Modifier
                            .align(Alignment.BottomEnd)
                            .padding(20.dp),
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                    ) {
                        Text("↑", style = MaterialTheme.typography.titleLarge)
                    }
                }
            }
        }
    }
}
