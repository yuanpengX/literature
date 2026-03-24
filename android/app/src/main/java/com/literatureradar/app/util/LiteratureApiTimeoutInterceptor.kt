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
        val longReadWrite = 300L to TimeUnit.SECONDS
        val llmSync = 120L to TimeUnit.SECONDS

        val c =
            when {
                path.contains("/feed") -> chain
                    .withReadTimeout(longReadWrite.first, longReadWrite.second)
                    .withWriteTimeout(longReadWrite.first, longReadWrite.second)
                path.contains("/users/me/llm") -> chain
                    .withReadTimeout(llmSync.first, llmSync.second)
                    .withWriteTimeout(llmSync.first, llmSync.second)
                path.contains("/daily-picks/me/run") -> chain
                    .withReadTimeout(longReadWrite.first, longReadWrite.second)
                    .withWriteTimeout(longReadWrite.first, longReadWrite.second)
                path.contains("/subscriptions/fetch-now") -> chain
                    .withReadTimeout(longReadWrite.first, longReadWrite.second)
                    .withWriteTimeout(longReadWrite.first, longReadWrite.second)
                else -> chain
            }
        return c.proceed(chain.request())
    }
}
