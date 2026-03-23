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
import com.literatureradar.app.util.NetworkErrorHumanizer
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.data.LiteratureClientConfigFetcher
import com.literatureradar.app.data.UserLlmCredentialsBody
import com.literatureradar.app.data.llm.LlmPresets
import com.literatureradar.app.prefs.AppPrefs
import com.literatureradar.app.work.DigestScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.literatureradar.app.R

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

    var llmHint by remember { mutableStateOf<String?>(null) }
    var dailyLlmHint by remember { mutableStateOf<String?>(null) }
    var literatureApiDomain by remember { mutableStateOf(AppPrefs.getApiBaseUrl(ctx)) }
    var useServerIp by remember { mutableStateOf(AppPrefs.isUseServerIpBase(ctx)) }
    var apiBaseHint by remember { mutableStateOf<String?>(null) }
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
            Text("文献 API 根地址", style = MaterialTheme.typography.titleMedium)
            Text(
                "默认走 HTTPS 域名（与 strings.xml 一致，可下方覆盖）。开启「IP」后使用服务端 server/.env 的 LITERATURE_HTTP_IP_BASE，需先能访问域名以拉取配置。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = literatureApiDomain,
                onValueChange = { literatureApiDomain = it },
                label = { Text("自定义域名根地址（可选）") },
                placeholder = { Text(ctx.getString(R.string.api_base_url)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
                singleLine = false,
            )
            Button(
                onClick = {
                    AppPrefs.setApiBaseUrl(ctx, literatureApiDomain.trim())
                    literatureApiDomain = AppPrefs.getApiBaseUrl(ctx)
                    ServiceLocator.rebuildNetworkIfNeeded()
                    apiBaseHint = "已保存域名根地址"
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("保存文献 API 域名")
            }
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.weight(1f)) {
                    Text("使用服务端 IP（HTTP）", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "从 /api/v1/config/client 读取；真机 HTTP 可能受系统限制。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = useServerIp,
                    onCheckedChange = { on ->
                        if (!on) {
                            AppPrefs.setUseServerIpBase(ctx, false)
                            useServerIp = false
                            ServiceLocator.rebuildNetworkIfNeeded()
                            apiBaseHint = "已切回域名模式"
                            return@Switch
                        }
                        scope.launch {
                            apiBaseHint = "正在拉取 IP 配置…"
                            val domainRoot =
                                AppPrefs.normalizeApiBaseUrl(
                                    AppPrefs.getApiBaseUrl(ctx).ifBlank { ctx.getString(R.string.api_base_url) },
                                ).ifEmpty {
                                    AppPrefs.normalizeApiBaseUrl(ctx.getString(R.string.api_base_url))
                                }
                            val ip =
                                withContext(Dispatchers.IO) {
                                    LiteratureClientConfigFetcher.fetchHttpIpBase(domainRoot)
                                }
                            if (ip == null) {
                                apiBaseHint =
                                    "拉取失败：请确认网络与 HTTPS 域名，且服务端已配置 LITERATURE_HTTP_IP_BASE"
                                return@launch
                            }
                            AppPrefs.setCachedHttpIpBase(ctx, ip)
                            AppPrefs.setUseServerIpBase(ctx, true)
                            useServerIp = true
                            ServiceLocator.rebuildNetworkIfNeeded()
                            apiBaseHint = "已启用 IP：$ip"
                        }
                    },
                )
            }
            if (useServerIp) {
                TextButton(
                    onClick = {
                        scope.launch {
                            apiBaseHint = "正在刷新…"
                            val domainRoot =
                                AppPrefs.normalizeApiBaseUrl(
                                    AppPrefs.getApiBaseUrl(ctx).ifBlank { ctx.getString(R.string.api_base_url) },
                                ).ifEmpty {
                                    AppPrefs.normalizeApiBaseUrl(ctx.getString(R.string.api_base_url))
                                }
                            val ip =
                                withContext(Dispatchers.IO) {
                                    LiteratureClientConfigFetcher.fetchHttpIpBase(domainRoot)
                                }
                            if (ip == null) {
                                apiBaseHint = "刷新失败"
                                return@launch
                            }
                            AppPrefs.setCachedHttpIpBase(ctx, ip)
                            ServiceLocator.rebuildNetworkIfNeeded()
                            apiBaseHint = "已更新：$ip"
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("从服务器刷新 IP 根地址")
                }
            }
            apiBaseHint?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

            Text("大模型（BYOK）", style = MaterialTheme.typography.titleMedium)
            Text(
                "端上「生成中文要点」直连模型商。若使用服务端「每日精选」与「推荐列表中文摘要（2～3 句）」，保存时需把 Key 同步到你信任的文献服务器（见下方说明）。",
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
                        scope.launch(Dispatchers.IO) {
                            val st = ServiceLocator.llmStore
                            if (st.apiKey.isBlank()) {
                                return@launch
                            }
                            val hint = runCatching {
                                ServiceLocator.api.putLlmCredentials(
                                    UserLlmCredentialsBody(
                                        baseUrl = st.resolvedOpenAiBaseRoot(),
                                        apiKey = st.apiKey.trim(),
                                        model = st.resolvedModel(),
                                    ),
                                )
                            }.fold(
                                onSuccess = { "已保存本机并已同步服务器（每日精选 + Feed 摘要）" },
                                onFailure = { e ->
                                    "已保存本机；同步服务器失败：${NetworkErrorHumanizer.message(e)}（仍可点「同步 LLM 到服务器」重试）"
                                },
                            )
                            withContext(Dispatchers.Main) { llmHint = hint }
                        }
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text("保存模型配置")
                }
                TextButton(
                    onClick = {
                        store.clearApiKey()
                        apiKey = ""
                        llmHint = "已清除本机 API Key"
                        scope.launch(Dispatchers.IO) {
                            runCatching { ServiceLocator.api.deleteLlmCredentials() }
                            withContext(Dispatchers.Main) {
                                llmHint = "已清除本机 Key，并已请求服务端删除 LLM 配置"
                            }
                        }
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

            Text("服务端 LLM（每日精选 / 推荐中文摘要）", style = MaterialTheme.typography.titleMedium)
            Text(
                "保存模型配置时会尝试自动同步，也可点下面按钮手动同步。服务器用你的 Key 跑每日精选，并在你打开推荐时为列表中的论文生成「简体中文 2～3 句」摘要（无摘要的条目不会出现在推荐列表）。请勿在不信任的服务器上同步密钥。",
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
                                    dailyLlmHint = "已同步 LLM 到服务器（每日精选 + Feed 摘要）"
                                }
                            }
                            .onFailure { e ->
                                withContext(Dispatchers.Main) {
                                    dailyLlmHint = NetworkErrorHumanizer.message(e)
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
