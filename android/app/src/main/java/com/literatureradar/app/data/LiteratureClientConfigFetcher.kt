package com.literatureradar.app.data

import com.literatureradar.app.prefs.AppPrefs
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * 通过当前可访问的「HTTPS 域名根」拉取服务端 [LITERATURE_HTTP_IP_BASE] 直连备用根地址（无需鉴权）。
 */
object LiteratureClientConfigFetcher {
    private val json = Json { ignoreUnknownKeys = true }

    private val client =
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .build()

    /** @return 规范化后的 http(s) 根地址；失败返回 null */
    fun fetchHttpIpBase(domainRoot: String): String? {
        val root = domainRoot.trimEnd('/')
        if (root.isEmpty()) return null
        val url = "$root/api/v1/config/client"
        val req = Request.Builder().url(url).get().build()
        return try {
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return null
                val body = resp.body?.string() ?: return null
                val cfg = json.decodeFromString<ClientConfigJson>(body)
                AppPrefs.normalizeApiBaseUrl(cfg.httpIpBase).takeIf { it.isNotEmpty() }
            }
        } catch (_: Exception) {
            null
        }
    }
}
