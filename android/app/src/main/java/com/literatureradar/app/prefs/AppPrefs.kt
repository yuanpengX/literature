package com.literatureradar.app.prefs

import android.content.Context
import com.literatureradar.app.R
import java.net.URI
import java.util.Locale

object AppPrefs {
    private const val PREFS = "literature_prefs"
    private const val KEY_DIGEST = "local_digest_enabled"
    private const val KEY_LAST_TOP_ID = "last_feed_top_id"
    /** 为空则使用 strings.xml 的 api_base_url（HTTPS 域名根；用于拉取服务端 IP 配置） */
    private const val KEY_API_BASE_URL = "api_base_url"
    /** 默认 false（未写入即不走直连）。裸 IP + HTTPS 常见证书域名不匹配，产品默认仅 HTTPS 域名。 */
    private const val KEY_USE_SERVER_IP = "api_use_server_ip_base"
    private const val KEY_CACHED_HTTP_IP_BASE = "api_http_ip_base_cached"
    /** 一次性迁移：强制回到「仅域名」策略，清除历史误开的直连与缓存 IP */
    private const val KEY_HTTPS_DOMAIN_DEFAULT_POLICY_APPLIED = "literature_https_domain_default_policy_v1"

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

    /**
     * 每个安装至多执行一次：关闭「服务端直连」、清空缓存的 `LITERATURE_HTTP_IP_BASE`，
     * 保证升级上来的用户与「默认未改设置」一致时只走 [R.string.api_base_url] 的 HTTPS 域名。
     * 仍需直连的用户可在设置里再次手动打开。
     */
    fun applyHttpsDomainDefaultPolicyOnce(ctx: Context) {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (p.getBoolean(KEY_HTTPS_DOMAIN_DEFAULT_POLICY_APPLIED, false)) return
        p.edit()
            .putBoolean(KEY_USE_SERVER_IP, false)
            .remove(KEY_CACHED_HTTP_IP_BASE)
            .putBoolean(KEY_HTTPS_DOMAIN_DEFAULT_POLICY_APPLIED, true)
            .apply()
    }

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

    /**
     * 与 [com.literatureradar.app.ServiceLocator.rebuildNetworkIfNeeded] 使用同一规则：
     * 未开「直连」时仅用 HTTPS 域名根；开启直连时用缓存的 LITERATURE_HTTP_IP_BASE（无效则回退域名）。
     * 返回无尾斜杠的 origin，供界面展示与 Retrofit base（再加 `/`）一致。
     */
    fun resolveLiteratureApiBase(ctx: Context): String {
        val defaultBase = ctx.getString(R.string.api_base_url)
        val fromPrefs = getApiBaseUrl(ctx).trim()
        val raw = (fromPrefs.ifBlank { defaultBase }).trim()
        var domainNorm = normalizeApiBaseUrl(raw)
        if (domainNorm.isEmpty()) {
            domainNorm = normalizeApiBaseUrl(defaultBase)
        }
        val normalized =
            if (isUseServerIpBase(ctx)) {
                val ipNorm = normalizeApiBaseUrl(getCachedHttpIpBase(ctx).trim())
                if (ipNorm.isNotEmpty()) ipNorm else domainNorm
            } else {
                domainNorm
            }
        return normalized.trimEnd('/')
    }
}
