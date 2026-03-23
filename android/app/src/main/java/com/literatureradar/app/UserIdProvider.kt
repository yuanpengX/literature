package com.literatureradar.app

import android.content.Context

object UserIdProvider {
    private const val PREFS = "literature_prefs"
    private const val KEY = "user_id"

    fun get(context: Context): String {
        val sp = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        var id = sp.getString(KEY, null)
        if (id.isNullOrBlank()) {
            id = "u-" + java.util.UUID.randomUUID().toString().take(12)
            sp.edit().putString(KEY, id).apply()
        }
        return id
    }
}
