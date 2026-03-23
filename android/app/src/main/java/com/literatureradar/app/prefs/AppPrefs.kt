package com.literatureradar.app.prefs

import android.content.Context

object AppPrefs {
    private const val PREFS = "literature_prefs"
    private const val KEY_DIGEST = "local_digest_enabled"
    private const val KEY_LAST_TOP_ID = "last_feed_top_id"
    /** 为空则使用 strings.xml 的 api_base_url */
    private const val KEY_API_BASE_URL = "api_base_url"

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
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_API_BASE_URL, url.trim())
            .apply()
    }
}
