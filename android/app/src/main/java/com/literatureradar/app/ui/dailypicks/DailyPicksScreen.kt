package com.literatureradar.app.ui.dailypicks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import com.literatureradar.app.data.DailyPickItemJson
import com.literatureradar.app.data.toEntity
import com.literatureradar.app.ui.components.PaperCard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DailyPicksScreen(
    onOpenPaper: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val analytics = ServiceLocator.analytics
    val dao = ServiceLocator.db.paperDao()
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var refreshing by remember { mutableStateOf(false) }
    var items by remember { mutableStateOf<List<DailyPickItemJson>>(emptyList()) }
    var pickDate by remember { mutableStateOf("") }
    var note by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var serverLlm by remember { mutableStateOf(false) }
    var subscriptionKeywords by remember { mutableStateOf<List<String>>(emptyList()) }

    suspend fun loadFromNetwork() {
        val r = ServiceLocator.api.getDailyPicks(date = null)
        pickDate = r.date
        items = r.items
        note = r.note
        error = r.error
        serverLlm = r.serverLlmConfigured
        subscriptionKeywords = r.subscriptionKeywords
        if (r.items.isNotEmpty()) {
            withContext(Dispatchers.IO) {
                dao.upsertAll(r.items.map { it.paper.toEntity() })
            }
        }
    }

    LaunchedEffect(Unit) {
        loading = true
        runCatching { loadFromNetwork() }
        loading = false
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("每日精选", style = MaterialTheme.typography.titleLarge) },
            )
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = refreshing,
            onRefresh = {
                scope.launch {
                    refreshing = true
                    runCatching { loadFromNetwork() }
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
                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        item {
                            Text(
                                "日期：$pickDate",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            if (!serverLlm) {
                                Text(
                                    "尚未向服务器同步 LLM。请在「设置」中点击「同步 LLM」，并设置订阅关键词；服务器定时任务才会为你生成精选。",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.error,
                                    modifier = Modifier.padding(top = 8.dp),
                                )
                            }
                            if (subscriptionKeywords.isNotEmpty()) {
                                Text(
                                    "已启用订阅关键词（与「设置 → 订阅配置」一致）：${subscriptionKeywords.joinToString("、")}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(top = 8.dp),
                                )
                            } else if (serverLlm) {
                                Text(
                                    "当前未启用订阅关键词；精选将不按关键词预筛。可在「设置 → 订阅配置」中添加。",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(top = 8.dp),
                                )
                            }
                            error?.let { err ->
                                Text(
                                    err,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.error,
                                    modifier = Modifier.padding(top = 8.dp),
                                )
                            }
                            note?.let { n ->
                                if (n.isNotBlank()) {
                                    Text(
                                        n,
                                        style = MaterialTheme.typography.bodyMedium,
                                        modifier = Modifier.padding(top = 8.dp),
                                    )
                                }
                            }
                            Button(
                                onClick = {
                                    scope.launch {
                                        refreshing = true
                                        runCatching {
                                            val r = ServiceLocator.api.runDailyPicksNow()
                                            pickDate = r.date
                                            items = r.items
                                            note = r.note
                                            error = r.error
                                            serverLlm = r.serverLlmConfigured
                                            subscriptionKeywords = r.subscriptionKeywords
                                            if (r.items.isNotEmpty()) {
                                                withContext(Dispatchers.IO) {
                                                    dao.upsertAll(r.items.map { it.paper.toEntity() })
                                                }
                                            }
                                        }
                                        refreshing = false
                                    }
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 12.dp),
                                enabled = serverLlm,
                            ) {
                                Text("立即生成今日精选（覆盖当日）")
                            }
                        }
                        if (items.isEmpty() && !loading) {
                            item {
                                Text(
                                    "今日暂无精选条目。请先在「设置」同步大模型；精选仅展示带「中文 2～3 句」推荐理由的论文，可点击上方「立即生成」或等待定时任务。",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        itemsIndexed(items, key = { _, row -> row.paper.id }) { index, row ->
                            PaperCard(
                                paper = row.paper,
                                position = index,
                                pickBlurb = row.pickBlurb.takeIf { it.isNotBlank() },
                                onClick = {
                                    analytics.log(
                                        AnalyticsEventJson(
                                            eventType = "paper_open",
                                            paperId = row.paper.id,
                                            surface = "daily_picks",
                                            position = index,
                                        ),
                                    )
                                    onOpenPaper(row.paper.id)
                                },
                            )
                        }
                    }
                }
            }
        }
    }
}
