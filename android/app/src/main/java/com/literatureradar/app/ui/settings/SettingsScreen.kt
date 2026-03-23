package com.literatureradar.app.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.literatureradar.app.R
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.data.UserLlmCredentialsBody
import com.literatureradar.app.data.llm.LlmPresets
import com.literatureradar.app.prefs.AppPrefs
import com.literatureradar.app.work.DigestScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onOpenAbout: () -> Unit = {},
    onOpenSubscriptionConfig: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val store = ServiceLocator.llmStore
    val ctx = LocalContext.current
    val prefs = remember {
        ctx.getSharedPreferences("literature_prefs", android.content.Context.MODE_PRIVATE)
    }

    var analyticsOn by remember { mutableStateOf(prefs.getBoolean("analytics_on", true)) }
    var digestOn by remember { mutableStateOf(AppPrefs.isLocalDigestEnabled(ctx)) }

    var providerId by remember { mutableStateOf(store.providerId) }
    var model by remember {
        mutableStateOf(
            store.model.ifEmpty { LlmPresets.byId(store.providerId).defaultModel },
        )
    }
    var baseOverride by remember { mutableStateOf(store.baseUrlOverride) }
    var apiKey by remember { mutableStateOf(store.apiKey) }
    var showKey by remember { mutableStateOf(false) }

    var providerMenu by remember { mutableStateOf(false) }

    var serverUrl by remember { mutableStateOf(AppPrefs.getApiBaseUrl(ctx)) }
    var backendHint by remember { mutableStateOf<String?>(null) }
    var llmHint by remember { mutableStateOf<String?>(null) }
    var dailyLlmHint by remember { mutableStateOf<String?>(null) }
    val scope = remember { CoroutineScope(Dispatchers.Main) }

    val preset = LlmPresets.byId(providerId)

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("设置", style = MaterialTheme.typography.titleLarge) },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("文献服务器", style = MaterialTheme.typography.titleMedium)
            Text(
                "填写服务根地址，例如 http://主机:8000；勿以 / 结尾，也不要带 /api/v1（接口路径里已含）。修改后点「应用」。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = serverUrl,
                onValueChange = { serverUrl = it },
                label = { Text("API Base URL") },
                placeholder = { Text(ctx.getString(R.string.api_base_url)) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = false,
                minLines = 2,
            )
            Button(
                onClick = {
                    val u = serverUrl.trim()
                    if (u.isNotEmpty() && !u.startsWith("http://") && !u.startsWith("https://")) {
                        backendHint = "地址需以 http:// 或 https:// 开头"
                        return@Button
                    }
                    val beforeNorm = u
                    AppPrefs.setApiBaseUrl(ctx, u)
                    val norm = if (u.isBlank()) "" else AppPrefs.normalizeApiBaseUrl(u)
                    serverUrl = norm
                    ServiceLocator.rebuildNetworkIfNeeded()
                    DigestScheduler.schedule(ctx)
                    backendHint = when {
                        beforeNorm.isNotBlank() &&
                            beforeNorm.trimEnd('/').lowercase() != norm.lowercase() ->
                            "已应用；已自动去掉末尾的 /api/v1 等重复路径"
                        else -> "已应用后端地址"
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("应用后端地址")
            }
            backendHint?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

            Text("大模型（BYOK）", style = MaterialTheme.typography.titleMedium)
            Text(
                "API Key 仅保存在本机加密存储，不会上传到文献雷达服务器。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            ExposedDropdownMenuBox(
                expanded = providerMenu,
                onExpandedChange = { providerMenu = it },
            ) {
                OutlinedTextField(
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor(),
                    readOnly = true,
                    value = preset.displayName,
                    onValueChange = {},
                    label = { Text("模型商") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = providerMenu) },
                    colors = ExposedDropdownMenuDefaults.outlinedTextFieldColors(),
                )
                ExposedDropdownMenu(
                    expanded = providerMenu,
                    onDismissRequest = { providerMenu = false },
                ) {
                    LlmPresets.all.forEach { p ->
                        DropdownMenuItem(
                            text = { Text(p.displayName) },
                            onClick = {
                                providerId = p.id
                                model = p.defaultModel
                                providerMenu = false
                            },
                        )
                    }
                }
            }

            OutlinedTextField(
                value = model,
                onValueChange = { model = it },
                label = { Text("模型 ID") },
                supportingText = {
                    Text("常用：${preset.suggestedModels.joinToString(", ")}")
                },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )

            OutlinedTextField(
                value = baseOverride,
                onValueChange = { baseOverride = it },
                label = { Text("自定义 Base URL（可选）") },
                placeholder = { Text("例：https://api.deepseek.com/v1") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )

            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                label = { Text("API Key") },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (showKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showKey = !showKey }) {
                        Text(if (showKey) "隐藏" else "显示")
                    }
                },
                minLines = 2,
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        store.providerId = providerId
                        store.model = model.trim()
                        store.baseUrlOverride = baseOverride.trim()
                        store.apiKey = apiKey.trim()
                        llmHint = "已保存到本机"
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text("保存模型配置")
                }
                TextButton(
                    onClick = {
                        store.clearApiKey()
                        apiKey = ""
                        llmHint = "已清除 API Key"
                    },
                ) {
                    Text("清除 Key")
                }
            }
            llmHint?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

            Text("订阅与抓取", style = MaterialTheme.typography.titleMedium)
            Text(
                "在此集中管理订阅关键词、期刊（服务端按刊名匹配 RSS）与关注会议列表；保存后参与推荐、每日精选与定时抓取。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(
                onClick = onOpenSubscriptionConfig,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("打开订阅配置")
            }

            Text("每日精选（服务端 LLM）", style = MaterialTheme.typography.titleMedium)
            Text(
                "服务器在设定时刻（默认每天 6:30，时区见服务端配置）用你的「订阅关键词」从 arXiv / 期刊 / 会议候选中筛文，并用你同步上来的 API Key 请求大模型选出约 10 篇。请勿在不信任的服务器上同步密钥。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(
                onClick = {
                    scope.launch(Dispatchers.IO) {
                        val st = ServiceLocator.llmStore
                        if (st.apiKey.isBlank()) {
                            withContext(Dispatchers.Main) {
                                dailyLlmHint = "请先在上方「大模型 BYOK」中填写 API Key"
                            }
                            return@launch
                        }
                        runCatching {
                            ServiceLocator.api.putLlmCredentials(
                                UserLlmCredentialsBody(
                                    baseUrl = st.resolvedOpenAiBaseRoot(),
                                    apiKey = st.apiKey.trim(),
                                    model = st.resolvedModel(),
                                ),
                            )
                        }
                            .onSuccess {
                                withContext(Dispatchers.Main) {
                                    dailyLlmHint = "已同步 LLM 到服务器（用于每日精选）"
                                }
                            }
                            .onFailure { e ->
                                withContext(Dispatchers.Main) {
                                    dailyLlmHint = e.message ?: "同步失败"
                                }
                            }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("同步 LLM 到服务器")
            }
            TextButton(
                onClick = {
                    scope.launch(Dispatchers.IO) {
                        runCatching { ServiceLocator.api.deleteLlmCredentials() }
                        withContext(Dispatchers.Main) {
                            dailyLlmHint = "已请求清除服务端 LLM（若曾同步过）"
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("清除服务端 LLM 配置")
            }
            dailyLlmHint?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

            Text("新论文提醒（本地）", style = MaterialTheme.typography.titleMedium)
            Text(
                "约每 4 小时在联网时拉取最新论文；若列表顶部与上次不同则发系统通知。不依赖云推送。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("启用定期检查", modifier = Modifier.weight(1f))
                Switch(
                    checked = digestOn,
                    onCheckedChange = {
                        digestOn = it
                        AppPrefs.setLocalDigestEnabled(ctx, it)
                        DigestScheduler.schedule(ctx)
                    },
                )
            }

            Text("数据分析（埋点）", style = MaterialTheme.typography.titleMedium)
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("参与产品改进", modifier = Modifier.weight(1f))
                Switch(
                    checked = analyticsOn,
                    onCheckedChange = {
                        analyticsOn = it
                        ServiceLocator.analytics.setEnabled(it)
                        prefs.edit().putBoolean("analytics_on", it).apply()
                    },
                )
            }

            Text("关于", style = MaterialTheme.typography.titleMedium)
            Button(
                onClick = onOpenAbout,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("关于本应用")
            }
        }
    }
}
