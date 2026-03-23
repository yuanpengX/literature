package com.literatureradar.app.data.llm

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class LlmClient(
    private val store: LlmSecureStore,
) {
    private val http = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    suspend fun summarizePaperChinese(title: String, abstract: String): Result<String> =
        withContext(Dispatchers.IO) {
            val key = store.apiKey.trim()
            if (key.isEmpty()) {
                return@withContext Result.failure(IllegalStateException("请先在设置中填写 API Key"))
            }
            val url = try {
                store.resolvedChatCompletionsUrl()
            } catch (e: Exception) {
                return@withContext Result.failure(e)
            }
            val model = store.resolvedModel()
            val userContent = buildString {
                appendLine("请用中文输出 4～6 条要点（使用「-」开头的列表），帮助快速理解下列论文。不要编造实验结果；若摘要信息不足请明确说明。")
                appendLine()
                appendLine("标题：$title")
                appendLine("摘要：$abstract")
            }
            val reqBody = ChatCompletionRequest(
                model = model,
                messages = listOf(
                    ChatMessage("system", "你是学术文献阅读助手，简洁准确，使用中文。"),
                    ChatMessage("user", userContent),
                ),
            )
            val bodyStr = json.encodeToString(ChatCompletionRequest.serializer(), reqBody)
            val body = bodyStr.toRequestBody("application/json; charset=utf-8".toMediaType())
            val request = Request.Builder()
                .url(url)
                .header("Authorization", "Bearer $key")
                .post(body)
                .build()
            runCatching {
                http.newCall(request).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (!resp.isSuccessful) {
                        throw IllegalStateException(parseErrorMessage(text))
                    }
                    val parsed = json.decodeFromString(ChatCompletionResponse.serializer(), text)
                    val content = parsed.choices.firstOrNull()?.message?.content?.trim()
                    if (content.isNullOrEmpty()) {
                        throw IllegalStateException("模型返回为空")
                    }
                    content
                }
            }
        }
}
