package com.literatureradar.app.util

import okhttp3.Interceptor
import okhttp3.Response
import java.io.IOException

/**
 * OkHttp 默认不会对 PUT 在「连接被重置」时自动重试；同步 LLM 为幂等写入，可安全重试一次。
 */
class LlmEndpointRetryInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val req = chain.request()
        val path = req.url.encodedPath
        if (!path.contains("/users/me/llm")) {
            return chain.proceed(req)
        }

        var last: IOException? = null
        repeat(2) { attempt ->
            try {
                return chain.proceed(req)
            } catch (e: IOException) {
                last = e
                if (attempt == 0) {
                    try {
                        Thread.sleep(500)
                    } catch (_: InterruptedException) {
                        Thread.currentThread().interrupt()
                    }
                }
            }
        }
        throw last ?: IOException("llm sync failed")
    }
}
