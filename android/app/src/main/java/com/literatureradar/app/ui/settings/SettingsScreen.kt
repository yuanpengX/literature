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
import com.literatureradar.app.data.PreferencesBody
import com.literatureradar.app.data.llm.LlmPresets
import com.literatureradar.app.prefs.AppPrefs
import com.literatureradar.app.work.DigestScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onOpenAbout: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val store = ServiceLocator.llmStore
    val ctx = LocalContext.current
    val prefs = remember {
        ctx.getSharedPreferences("literature_prefs", android.content.Context.MODE_PRIVATE)
    }

    var keywords by remember { mutableStateOf("") }
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
    var savedHint by remember { mutableStateOf<String?>(null) }
    var llmHint by remember { mutableStateOf<String?>(null) }
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
                "填写 Docker / 本机 API 根地址，勿以 / 结尾。留空则使用默认（见占位）。修改后点「应用」。",
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
                    AppPrefs.setApiBaseUrl(ctx, u)
                    ServiceLocator.rebuildNetworkIfNeeded()
                    DigestScheduler.schedule(ctx)
                    backendHint = "已应用后端地址"
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

            Text("订阅偏好", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = keywords,
                onValueChange = { keywords = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
                placeholder = { Text("关键词，逗号分隔，同步到服务端") },
            )
            Button(
                onClick = {
                    scope.launch(Dispatchers.IO) {
                        runCatching {
                            ServiceLocator.api.putPreferences(PreferencesBody(keywords = keywords.trim()))
                        }
                    }
                    savedHint = "已尝试同步偏好（需网络）"
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("保存并同步关键词")
            }
            savedHint?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

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
