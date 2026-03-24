package com.literatureradar.app.util

import okhttp3.Interceptor
import okhttp3.Response
import java.util.concurrent.TimeUnit

/**
 * 按路径拉长读/写超时，与 Caddy `read_timeout` 及慢路径（ingest 占库、LLM 等）对齐。
 */
class LiteratureApiTimeoutInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val path = chain.request().url.encodedPath
        // OkHttp Chain.withReadTimeout/WriteTimeout 第一参数为 Int（与 Java 重载一致），勿用 Long 字面量
        val longReadWriteSec = 300
        val llmSyncSec = 120

        val c =
            when {
                path.contains("/feed") -> chain
                    .withReadTimeout(longReadWriteSec, TimeUnit.SECONDS)
                    .withWriteTimeout(longReadWriteSec, TimeUnit.SECONDS)
                path.contains("/users/me/llm") -> chain
                    .withReadTimeout(llmSyncSec, TimeUnit.SECONDS)
                    .withWriteTimeout(llmSyncSec, TimeUnit.SECONDS)
                path.contains("/daily-picks/me/run") -> chain
                    .withReadTimeout(longReadWriteSec, TimeUnit.SECONDS)
                    .withWriteTimeout(longReadWriteSec, TimeUnit.SECONDS)
                path.contains("/subscriptions/fetch-now") -> chain
                    .withReadTimeout(longReadWriteSec, TimeUnit.SECONDS)
                    .withWriteTimeout(longReadWriteSec, TimeUnit.SECONDS)
                else -> chain
            }
        return c.proceed(chain.request())
    }
}
