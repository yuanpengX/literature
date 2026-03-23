package com.literatureradar.app.data

private val TAG_REGEX = Regex("<[^>]+>", RegexOption.IGNORE_CASE)

/** 期刊 RSS 等可能含 HTML；与服务端 strip 一致化，并兼容 Room 里旧缓存。 */
fun String.stripHtmlToPlain(): String {
    if (isBlank()) return trim()
    var s = replace(TAG_REGEX, " ")
    s = s.replace("&nbsp;", " ", ignoreCase = true)
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&apos;", "'")
    return s.replace(Regex("\\s+"), " ").trim()
}

private fun String.normalizedForCompare(): String =
    lowercase().replace(Regex("\\s+"), " ").trim()

/** 一句话与摘要正文实质相同时不双显（与服务端一致） */
fun feedBlurbRedundantWithAbstract(blurb: String, abstractPlain: String): Boolean {
    val b = blurb.normalizedForCompare()
    val a = abstractPlain.normalizedForCompare()
    if (b.isEmpty() || a.isEmpty()) return false
    if (b == a) return true
    if (b.length >= 20 && a.startsWith(b) && (a.length - b.length) <= 24) return true
    if (a.length >= 20 && b.startsWith(a) && (b.length - a.length) <= 24) return true
    return false
}
