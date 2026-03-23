package com.literatureradar.app.ui.detail

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarBorder
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.data.AnalyticsEventJson
import com.literatureradar.app.data.PaperJson
import com.literatureradar.app.data.local.FavoriteEntity
import com.literatureradar.app.data.toEntity
import com.literatureradar.app.data.toPaperJson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PaperDetailScreen(
    paperId: Int,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val dao = ServiceLocator.db.paperDao()
    val favoriteDao = ServiceLocator.db.favoriteDao()
    val analytics = ServiceLocator.analytics
    val llm = ServiceLocator.llmClient
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var paper by remember { mutableStateOf<PaperJson?>(null) }
    var loading by remember { mutableStateOf(true) }
    var err by remember { mutableStateOf<String?>(null) }

    var aiSummary by remember { mutableStateOf<String?>(null) }
    var aiLoading by remember { mutableStateOf(false) }
    var aiError by remember { mutableStateOf<String?>(null) }
    var isFavorite by remember { mutableStateOf(false) }

    LaunchedEffect(paperId) {
        isFavorite = withContext(Dispatchers.IO) {
            favoriteDao.countFor(paperId) > 0
        }
        aiSummary = null
        aiError = null
        err = null
        withContext(Dispatchers.IO) {
            val cached = dao.getById(paperId)
            if (cached != null) {
                withContext(Dispatchers.Main) {
                    paper = cached.toPaperJson()
                    loading = false
                }
            }
        }
        if (paper == null) loading = true
        runCatching { ServiceLocator.api.getPaper(paperId) }
            .onSuccess { remote ->
                paper = remote
                withContext(Dispatchers.IO) {
                    dao.upsertAll(listOf(remote.toEntity()))
                }
                err = null
            }
            .onFailure { e ->
                if (paper == null) err = e.message ?: "加载失败"
            }
        loading = false
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("论文详情", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(
                        onClick = {
                            scope.launch {
                                val next = !isFavorite
                                withContext(Dispatchers.IO) {
                                    if (next) {
                                        favoriteDao.upsert(
                                            FavoriteEntity(paperId, System.currentTimeMillis()),
                                        )
                                    } else {
                                        favoriteDao.deleteByPaperId(paperId)
                                    }
                                }
                                isFavorite = next
                                analytics.log(
                                    AnalyticsEventJson(
                                        eventType = if (next) "save" else "unsave",
                                        paperId = paperId,
                                    ),
                                )
                            }
                        },
                    ) {
                        Icon(
                            imageVector = if (isFavorite) Icons.Filled.Star else Icons.Outlined.StarBorder,
                            contentDescription = if (isFavorite) "取消收藏" else "收藏",
                        )
                    }
                },
            )
        },
    ) { padding ->
        when {
            loading && paper == null -> {
                Box(
                    Modifier
                        .fillMaxSize()
                        .padding(padding),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator()
                }
            }
            err != null && paper == null -> {
                Text(err!!, Modifier.padding(padding).padding(16.dp))
            }
            paper != null -> {
                val p = paper!!
                Column(
                    Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(p.title, style = MaterialTheme.typography.titleLarge)
                    Text("${p.source} · ${p.externalId}", style = MaterialTheme.typography.labelSmall)
                    if (p.citationCount > 0) {
                        Text(
                            "引用（OpenAlex）${p.citationCount}",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text("摘要", style = MaterialTheme.typography.titleMedium)
                    Text(p.abstract, style = MaterialTheme.typography.bodyLarge)

                    Text("AI 要点（端上模型）", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "内容由大模型根据摘要生成，仅供速览；请以原文为准。需在设置中配置自备 API Key。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (aiLoading) {
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                    }
                    aiError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    aiSummary?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
                    OutlinedButton(
                        onClick = {
                            aiError = null
                            aiLoading = true
                            scope.launch {
                                val r = withContext(Dispatchers.IO) {
                                    llm.summarizePaperChinese(p.title, p.abstract)
                                }
                                aiLoading = false
                                r.onSuccess { aiSummary = it }
                                    .onFailure { aiError = it.message ?: "生成失败" }
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !aiLoading,
                    ) {
                        Text("生成中文要点")
                    }

                    p.pdfUrl?.let { url ->
                        Button(
                            onClick = {
                                analytics.log(
                                    AnalyticsEventJson(
                                        eventType = "open_external_link",
                                        paperId = p.id,
                                        payload = mapOf("kind" to "pdf"),
                                    ),
                                )
                                ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("打开 PDF")
                        }
                    }
                    p.htmlUrl?.let { url ->
                        Button(
                            onClick = {
                                analytics.log(
                                    AnalyticsEventJson(
                                        eventType = "open_external_link",
                                        paperId = p.id,
                                        payload = mapOf("kind" to "html"),
                                    ),
                                )
                                ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("原文链接")
                        }
                    }
                }
            }
        }
    }
}
