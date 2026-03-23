package com.literatureradar.app.prefs

import android.content.Context
import java.net.URI
import java.util.Locale

object AppPrefs {
    private const val PREFS = "literature_prefs"
    private const val KEY_DIGEST = "local_digest_enabled"
    private const val KEY_LAST_TOP_ID = "last_feed_top_id"
    /** 为空则使用 strings.xml 的 api_base_url（HTTPS 域名根；用于拉取服务端 IP 配置） */
    private const val KEY_API_BASE_URL = "api_base_url"
    private const val KEY_USE_SERVER_IP = "api_use_server_ip_base"
    private const val KEY_CACHED_HTTP_IP_BASE = "api_http_ip_base_cached"

    /**
     * Retrofit 接口路径已带 `api/v1/...`。
     * 规范化：去空白、补 https://、去掉重复 scheme、去掉默认 80/443 端口、剥掉误带的 `/api/v1`。
     */
    fun normalizeApiBaseUrl(raw: String): String {
        var s = raw.trim().replace(Regex("\\s+"), "")
        if (s.isEmpty()) return ""
        while (s.startsWith("https://https://", ignoreCase = true)) {
            s = s.removePrefix("https://")
        }
        while (s.startsWith("http://http://", ignoreCase = true)) {
            s = s.removePrefix("http://")
        }
        if (!s.startsWith("http://", ignoreCase = true) && !s.startsWith("https://", ignoreCase = true)) {
            s = "https://$s"
        }
        val uri = try {
            URI(s)
        } catch (_: Exception) {
            return ""
        }
        val scheme = when (uri.scheme?.lowercase(Locale.US)) {
            "http" -> "http"
            else -> "https"
        }
        val host = uri.host?.takeIf { it.isNotBlank() } ?: return ""
        val port = uri.port
        val defaultPort = if (scheme == "https") 443 else 80
        val authority =
            if (port in 1..65534 && port != defaultPort) "$host:$port" else host
        // 文献 API 根地址仅使用 origin，忽略误粘贴的路径，避免与 Retrofit 的 /api/v1/... 重复拼接
        val base = "$scheme://$authority"
        return stripApiVersionSuffix(base)
    }

    private fun stripApiVersionSuffix(u: String): String {
        var x = u.trimEnd('/')
        while (x.isNotEmpty()) {
            val low = x.lowercase(Locale.US)
            when {
                low.endsWith("/api/v1") -> x = x.dropLast(7).trimEnd('/')
                low.endsWith("/api/v2") -> x = x.dropLast(7).trimEnd('/')
                else -> break
            }
        }
        return x.trimEnd('/')
    }

    fun isLocalDigestEnabled(ctx: Context): Boolean =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_DIGEST, true)

    fun setLocalDigestEnabled(ctx: Context, on: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean(KEY_DIGEST, on)
            .apply()
    }

    fun getLastFeedTopId(ctx: Context): Int =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getInt(KEY_LAST_TOP_ID, -1)

    fun setLastFeedTopId(ctx: Context, id: Int) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putInt(KEY_LAST_TOP_ID, id)
            .apply()
    }

    fun getApiBaseUrl(ctx: Context): String =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_API_BASE_URL, "") ?: ""

    fun setApiBaseUrl(ctx: Context, url: String) {
        val stored = if (url.isBlank()) "" else normalizeApiBaseUrl(url)
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_API_BASE_URL, stored)
            .apply()
    }

    fun isUseServerIpBase(ctx: Context): Boolean =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_USE_SERVER_IP, false)

    fun setUseServerIpBase(ctx: Context, on: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean(KEY_USE_SERVER_IP, on)
            .apply()
    }

    fun getCachedHttpIpBase(ctx: Context): String =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_CACHED_HTTP_IP_BASE, "") ?: ""

    fun setCachedHttpIpBase(ctx: Context, url: String) {
        val stored = if (url.isBlank()) "" else normalizeApiBaseUrl(url)
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_CACHED_HTTP_IP_BASE, stored)
            .apply()
    }
}
