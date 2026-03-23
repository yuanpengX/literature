package com.literatureradar.app.data.llm

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

private val errorJson = Json { ignoreUnknownKeys = true }

@Serializable
data class ChatCompletionRequest(
    val model: String,
    val messages: List<ChatMessage>,
    val temperature: Double = 0.35,
)

@Serializable
data class ChatMessage(
    val role: String,
    val content: String,
)

@Serializable
data class ChatCompletionResponse(
    val choices: List<ChatChoice> = emptyList(),
)

@Serializable
data class ChatChoice(
    val message: ChatMessage? = null,
)

fun parseErrorMessage(body: String?): String {
    if (body.isNullOrBlank()) return "未知错误"
    return try {
        val root = errorJson.parseToJsonElement(body).jsonObject
        val err = root["error"] ?: return body.take(200)
        when (err) {
            is JsonObject -> err["message"]?.jsonPrimitive?.content ?: body.take(200)
            is JsonPrimitive -> err.content
            else -> body.take(200)
        }
    } catch (_: Exception) {
        body.take(200)
    }
}
