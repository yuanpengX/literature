package com.literatureradar.app.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.data.ConferencePresetJson
import com.literatureradar.app.data.JournalPresetJson
import com.literatureradar.app.data.SubscriptionCatalogJson
import com.literatureradar.app.data.SubscriptionConferenceItemJson
import com.literatureradar.app.data.SubscriptionJournalItemJson
import com.literatureradar.app.data.SubscriptionKeywordItemJson
import com.literatureradar.app.data.UserSubscriptionsJson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SubscriptionConfigScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scope = rememberCoroutineScope()
    val api = ServiceLocator.api

    var catalog by remember { mutableStateOf<SubscriptionCatalogJson?>(null) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var hint by remember { mutableStateOf<String?>(null) }

    val keywordItems = remember { mutableStateListOf<SubscriptionKeywordItemJson>() }
    val journalItems = remember { mutableStateListOf<SubscriptionJournalItemJson>() }
    val conferenceItems = remember { mutableStateListOf<SubscriptionConferenceItemJson>() }

    var tab by remember { mutableIntStateOf(0) }
    var newKeyword by remember { mutableStateOf("") }
    var addJournalOpen by remember { mutableStateOf(false) }
    var addConferenceOpen by remember { mutableStateOf(false) }

    fun journalPreset(id: String): JournalPresetJson? =
        catalog?.journals?.find { it.id == id }

    fun conferencePreset(id: String): ConferencePresetJson? =
        catalog?.conferences?.find { it.id == id }

    LaunchedEffect(Unit) {
        loadError = null
        try {
            val cat = withContext(Dispatchers.IO) { api.getSubscriptionCatalog() }
            val me = withContext(Dispatchers.IO) { api.getMySubscriptions() }
            catalog = cat
            keywordItems.clear()
            keywordItems.addAll(me.keywords)
            journalItems.clear()
            journalItems.addAll(me.journals)
            conferenceItems.clear()
            conferenceItems.addAll(me.conferences)
        } catch (e: Exception) {
            loadError = e.message ?: "加载失败"
        }
    }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("订阅配置", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
        ) {
            Text(
                "按期刊名使用服务端预设的 RSS；关键词用于推荐与每日精选；会议为关注列表（论文多来自 OpenAlex / arXiv 等，后续可扩展专用源）。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(vertical = 8.dp),
            )

            loadError?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }

            TabRow(selectedTabIndex = tab) {
                Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("期刊") })
                Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("会议") })
                Tab(selected = tab == 2, onClick = { tab = 2 }, text = { Text("关键词") })
            }

            when (tab) {
                0 -> {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("期刊", style = MaterialTheme.typography.titleMedium)
                        TextButton(
                            onClick = { addJournalOpen = true },
                            enabled = catalog != null,
                        ) {
                            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                            Text("添加")
                        }
                    }
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.weight(1f),
                    ) {
                        items(journalItems.size, key = { journalItems[it].id }) { idx ->
                            val item = journalItems[idx]
                            val p = journalPreset(item.id)
                            Row(
                                Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(Modifier.weight(1f)) {
                                    Text(
                                        p?.name ?: item.id,
                                        style = MaterialTheme.typography.bodyLarge,
                                    )
                                    Text(
                                        listOfNotNull(p?.abbr, p?.issn).joinToString(" · "),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Switch(
                                    checked = item.enabled,
                                    onCheckedChange = { v ->
                                        journalItems[idx] = item.copy(enabled = v)
                                    },
                                )
                                IconButton(onClick = { journalItems.removeAt(idx) }) {
                                    Icon(Icons.Default.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.error)
                                }
                            }
                        }
                    }
                }
                1 -> {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("会议", style = MaterialTheme.typography.titleMedium)
                        TextButton(
                            onClick = { addConferenceOpen = true },
                            enabled = catalog != null,
                        ) {
                            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.padding(end = 4.dp))
                            Text("添加")
                        }
                    }
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.weight(1f),
                    ) {
                        items(conferenceItems.size, key = { conferenceItems[it].id }) { idx ->
                            val item = conferenceItems[idx]
                            val p = conferencePreset(item.id)
                            Row(
                                Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(Modifier.weight(1f)) {
                                    Text(p?.name ?: item.id, style = MaterialTheme.typography.bodyLarge)
                                    p?.note?.takeIf { it.isNotBlank() }?.let { n ->
                                        Text(
                                            n,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                                Switch(
                                    checked = item.enabled,
                                    onCheckedChange = { v ->
                                        conferenceItems[idx] = item.copy(enabled = v)
                                    },
                                )
                                IconButton(onClick = { conferenceItems.removeAt(idx) }) {
                                    Icon(Icons.Default.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.error)
                                }
                            }
                        }
                    }
                }
                else -> {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        OutlinedTextField(
                            value = newKeyword,
                            onValueChange = { newKeyword = it },
                            modifier = Modifier.weight(1f),
                            singleLine = true,
                            label = { Text("新关键词") },
                            placeholder = { Text("例如：molecular docking") },
                        )
                        Button(
                            onClick = {
                                val t = newKeyword.trim()
                                if (t.isNotEmpty()) {
                                    keywordItems.add(SubscriptionKeywordItemJson(text = t, enabled = true))
                                    newKeyword = ""
                                }
                            },
                            modifier = Modifier.padding(top = 8.dp),
                        ) {
                            Text("添加")
                        }
                    }
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.weight(1f),
                    ) {
                        items(keywordItems.size, key = { "${keywordItems[it].text}-$it" }) { idx ->
                            val item = keywordItems[idx]
                            Row(
                                Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text(item.text, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                                Switch(
                                    checked = item.enabled,
                                    onCheckedChange = { v ->
                                        keywordItems[idx] = item.copy(enabled = v)
                                    },
                                )
                                IconButton(onClick = { keywordItems.removeAt(idx) }) {
                                    Icon(Icons.Default.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.error)
                                }
                            }
                        }
                    }
                }
            }

            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                TextButton(
                    onClick = {
                        val c = catalog ?: return@TextButton
                        keywordItems.clear()
                        keywordItems.addAll(c.defaultKeywords)
                        journalItems.clear()
                        journalItems.addAll(c.defaultJournals)
                        conferenceItems.clear()
                        conferenceItems.addAll(c.defaultConferences)
                        hint = "已填入推荐配置（AI / 药物发现 / 分子设计），请点「保存到服务器」"
                    },
                    enabled = catalog != null,
                ) {
                    Text("恢复推荐配置")
                }
            }

            Button(
                onClick = {
                    scope.launch(Dispatchers.IO) {
                        runCatching {
                            api.putMySubscriptions(
                                UserSubscriptionsJson(
                                    keywords = keywordItems.toList(),
                                    journals = journalItems.toList(),
                                    conferences = conferenceItems.toList(),
                                ),
                            )
                        }
                            .onSuccess {
                                withContext(Dispatchers.Main) {
                                    hint = "已保存"
                                }
                            }
                            .onFailure { e ->
                                withContext(Dispatchers.Main) {
                                    hint = e.message ?: "保存失败"
                                }
                            }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 16.dp),
            ) {
                Text("保存到服务器")
            }
            hint?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    }

    if (addJournalOpen && catalog != null) {
        val existing = journalItems.map { it.id }.toSet()
        val choices = catalog!!.journals.filter { it.id !in existing }
        AlertDialog(
            onDismissRequest = { addJournalOpen = false },
            title = { Text("添加期刊") },
            text = {
                LazyColumn(modifier = Modifier.heightIn(max = 360.dp)) {
                    items(choices.size, key = { choices[it].id }) { i ->
                        val p = choices[i]
                        TextButton(
                            onClick = {
                                journalItems.add(SubscriptionJournalItemJson(id = p.id, enabled = true))
                                addJournalOpen = false
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("${p.name} (${p.abbr})")
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { addJournalOpen = false }) { Text("关闭") }
            },
        )
    }

    if (addConferenceOpen && catalog != null) {
        val existing = conferenceItems.map { it.id }.toSet()
        val choices = catalog!!.conferences.filter { it.id !in existing }
        AlertDialog(
            onDismissRequest = { addConferenceOpen = false },
            title = { Text("添加会议") },
            text = {
                LazyColumn(modifier = Modifier.heightIn(max = 360.dp)) {
                    items(choices.size, key = { choices[it].id }) { i ->
                        val p = choices[i]
                        TextButton(
                            onClick = {
                                conferenceItems.add(SubscriptionConferenceItemJson(id = p.id, enabled = true))
                                addConferenceOpen = false
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(p.name)
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { addConferenceOpen = false }) { Text("关闭") }
            },
        )
    }
}
