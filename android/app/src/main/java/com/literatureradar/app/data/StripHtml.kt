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
