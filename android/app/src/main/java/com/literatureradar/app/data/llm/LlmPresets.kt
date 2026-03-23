package com.literatureradar.app.data.llm

data class LlmPreset(
    val id: String,
    val displayName: String,
    /** OpenAI 兼容根路径，不含末尾斜杠也可 */
    val defaultBaseUrl: String,
    val defaultModel: String,
    val suggestedModels: List<String>,
)

object LlmPresets {
    val all: List<LlmPreset> = listOf(
        LlmPreset(
            id = "deepseek",
            displayName = "DeepSeek",
            defaultBaseUrl = "https://api.deepseek.com/v1",
            defaultModel = "deepseek-chat",
            suggestedModels = listOf("deepseek-chat", "deepseek-coder"),
        ),
        LlmPreset(
            id = "moonshot",
            displayName = "Kimi (Moonshot)",
            defaultBaseUrl = "https://api.moonshot.cn/v1",
            defaultModel = "moonshot-v1-8k",
            suggestedModels = listOf("moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"),
        ),
        LlmPreset(
            id = "custom",
            displayName = "自定义 Base URL",
            defaultBaseUrl = "",
            defaultModel = "gpt-4o-mini",
            suggestedModels = listOf("gpt-4o-mini", "deepseek-chat"),
        ),
    )

    fun byId(id: String): LlmPreset = all.find { it.id == id } ?: all.first()
}
