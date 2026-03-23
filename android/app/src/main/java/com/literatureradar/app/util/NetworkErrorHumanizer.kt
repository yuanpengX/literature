package com.literatureradar.app.util

/**
 * 将 OkHttp / java.net 的英文连接错误转成可读中文。
 *
 * 常见误读：「Failed to connect to cppteam.cn/150.158.x.x:443」里的 **斜杠不是 URL 拼接**，
 * 而是系统写法「主机名 / 解析到的 IP : 端口」；实际请求仍是 https://cppteam.cn/...
 */
object NetworkErrorHumanizer {

    fun message(e: Throwable): String {
        val blob = buildString {
            var x: Throwable? = e
            var depth = 0
            while (x != null && depth < 6) {
                x.message?.trim()?.takeIf { it.isNotEmpty() }?.let { append('\n').append(it) }
                x = x.cause
                depth++
            }
        }.trim()

        humanizeBlob(blob)?.let { return it }

        return e.message?.trim()?.takeIf { it.isNotEmpty() } ?: "请求失败"
    }

    private fun humanizeBlob(blob: String): String? {
        val t = blob

        Regex(
            """(?i)Failed to connect to\s+([^/\s]+)/([^:\s]+):(\d+)""",
        ).find(t)?.let { m ->
            val host = m.groupValues[1]
            val ip = m.groupValues[2]
            val port = m.groupValues[3]
            return "无法连接 $host（HTTPS 端口 $port）。「$host/$ip」是系统显示的「域名与解析到的 IP」，不是把地址拼错了；请检查手机网络、服务器 443 与防火墙。"
        }

        Regex(
            """(?i)failed to connect to\s+([^/\s]+)/([^:\s]+)\s*\(\s*port\s+(\d+)\s*\)""",
        ).find(t)?.let { m ->
            val host = m.groupValues[1]
            val ip = m.groupValues[2]
            val port = m.groupValues[3]
            return "无法连接 $host（端口 $port）。「$host/$ip」为系统诊断信息，并非 URL 拼接错误；请检查服务与网络。"
        }

        if (t.contains("Unable to resolve host", ignoreCase = true)) {
            return "无法解析域名，请检查 DNS 与网络"
        }
        if (t.contains("SSLHandshakeException", ignoreCase = true) ||
            t.contains("Certificate", ignoreCase = true) ||
            t.contains("CertPathValidatorException", ignoreCase = true)
        ) {
            return "HTTPS 证书校验失败，请确认使用受信任证书与正确域名"
        }
        if (t.contains("timeout", ignoreCase = true) || t.contains("timed out", ignoreCase = true)) {
            return "连接超时，请稍后重试或检查网络"
        }
        return null
    }
}
