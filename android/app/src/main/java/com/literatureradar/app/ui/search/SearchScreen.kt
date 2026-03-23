package com.literatureradar.app.ui.search

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.data.AnalyticsEventJson
import com.literatureradar.app.data.PaperJson
import com.literatureradar.app.data.toEntity
import com.literatureradar.app.ui.components.PaperCard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    onOpenPaper: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val dao = ServiceLocator.db.paperDao()
    val analytics = ServiceLocator.analytics
    val scope = rememberCoroutineScope()
    var query by remember { mutableStateOf("") }
    var items by remember { mutableStateOf<List<PaperJson>>(emptyList()) }
    var searched by remember { mutableStateOf(false) }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("主题搜索", style = MaterialTheme.typography.titleLarge) },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("关键词") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Button(
                onClick = {
                    if (query.isBlank()) return@Button
                    analytics.log(
                        AnalyticsEventJson(
                            eventType = "search_query",
                            payload = mapOf("q_len" to query.length.toString()),
                        ),
                    )
                    searched = true
                    scope.launch {
                        runCatching {
                            val res = ServiceLocator.api.search(q = query.trim(), limit = 40)
                            items = res.items
                            if (res.items.isNotEmpty()) {
                                withContext(Dispatchers.IO) {
                                    dao.upsertAll(res.items.map { it.toEntity() })
                                }
                            }
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("搜索")
            }
            if (searched && items.isEmpty()) {
                Text("无结果，可换词重试。", style = MaterialTheme.typography.bodyMedium)
            }
            LazyColumn(
                contentPadding = PaddingValues(vertical = 8.dp),
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
                                    surface = "search",
                                    position = index,
                                ),
                            )
                            onOpenPaper(paper.id)
                        },
                    )
                }
            }
        }
    }
}
