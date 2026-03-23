package com.literatureradar.app.prefs

import android.content.Context
import java.util.Locale

object AppPrefs {
    private const val PREFS = "literature_prefs"
    private const val KEY_DIGEST = "local_digest_enabled"
    private const val KEY_LAST_TOP_ID = "last_feed_top_id"
    /** 为空则使用 strings.xml 的 api_base_url */
    private const val KEY_API_BASE_URL = "api_base_url"

    /**
     * Retrofit 接口路径已带 `api/v1/...`。
     * 若用户填写 `http://host:8000/api/v1`，会变成 `.../api/v1/api/v1/...` 导致 404。
     */
    fun normalizeApiBaseUrl(raw: String): String {
        var u = raw.trim().trimEnd('/')
        while (u.isNotEmpty()) {
            val low = u.lowercase(Locale.US)
            if (low.endsWith("/api/v1")) {
                u = u.dropLast(7).trimEnd('/')
                continue
            }
            if (low.endsWith("/api/v2")) {
                u = u.dropLast(7).trimEnd('/')
                continue
            }
            break
        }
        return u.trimEnd('/')
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
}
