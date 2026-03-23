package com.literatureradar.app.util

import okhttp3.Interceptor
import okhttp3.Response
import java.util.concurrent.TimeUnit

/**
 * GET /feed 可能含多轮服务端 LLM，需与 Caddy read_timeout（如 300s）对齐，避免 OkHttp 60s 先断。
 */
class FeedTimeoutInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val path = chain.request().url.encodedPath
        val c =
            if (path.contains("/feed")) {
                chain
                    .withReadTimeout(300, TimeUnit.SECONDS)
                    .withWriteTimeout(300, TimeUnit.SECONDS)
            } else {
                chain
            }
        return c.proceed(chain.request())
    }
}
