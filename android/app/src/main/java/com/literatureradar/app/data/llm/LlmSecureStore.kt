package com.literatureradar.app.data.llm

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys

/**
 * 使用 EncryptedSharedPreferences 保存用户自备 API Key 与模型配置（仅存本机）。
 * （security-crypto 1.0.x：MasterKeys + create 文件名/别名/context）
 */
class LlmSecureStore(context: Context) {

    private val prefs: SharedPreferences

    init {
        val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
        prefs = EncryptedSharedPreferences.create(
            "llm_secure_prefs",
            masterKeyAlias,
            context.applicationContext,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var providerId: String
        get() = prefs.getString(KEY_PROVIDER, "deepseek") ?: "deepseek"
        set(value) {
            prefs.edit().putString(KEY_PROVIDER, value).apply()
        }

    var model: String
        get() = prefs.getString(KEY_MODEL, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_MODEL, value).apply()
        }

    /** 覆盖预设的 OpenAI 兼容根路径，需含 /v1，如 https://api.xxx.com/v1 */
    var baseUrlOverride: String
        get() = prefs.getString(KEY_BASE_OVERRIDE, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_BASE_OVERRIDE, value.trim()).apply()
        }

    var apiKey: String
        get() = prefs.getString(KEY_API_KEY, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_API_KEY, value).apply()
        }

    fun clearApiKey() {
        prefs.edit().remove(KEY_API_KEY).apply()
    }

    fun resolvedModel(): String {
        val m = model.trim()
        if (m.isNotEmpty()) return m
        return LlmPresets.byId(providerId).defaultModel
    }

    fun resolvedChatCompletionsUrl(): String {
        val override = baseUrlOverride.trim().trimEnd('/')
        val base = if (override.isNotEmpty()) {
            override
        } else {
            LlmPresets.byId(providerId).defaultBaseUrl.trim().trimEnd('/')
        }
        if (base.isEmpty()) {
            throw IllegalStateException("请填写自定义 Base URL（需指向 OpenAI 兼容 /v1）")
        }
        return "$base/chat/completions"
    }

    companion object {
        private const val KEY_PROVIDER = "provider_id"
        private const val KEY_MODEL = "model"
        private const val KEY_BASE_OVERRIDE = "base_url_override"
        private const val KEY_API_KEY = "api_key"
    }
}
