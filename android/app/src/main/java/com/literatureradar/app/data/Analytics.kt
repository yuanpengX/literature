package com.literatureradar.app.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.ArrayDeque

/**
 * 全局单例：切换后端 Base URL 时只 [bind] 新 [LiteratureApi]，不重复启动定时 flush 协程。
 */
class Analytics internal constructor() {

    @Volatile
    private var api: LiteratureApi? = null

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val queue = ArrayDeque<AnalyticsEventJson>()
    private val mutex = Mutex()

    @Volatile
    private var enabled: Boolean = true

    init {
        scope.launch {
            while (true) {
                delay(25_000)
                flush()
            }
        }
    }

    fun bind(next: LiteratureApi) {
        api = next
    }

    fun setEnabled(on: Boolean) {
        enabled = on
        if (!on) {
            scope.launch {
                mutex.withLock { queue.clear() }
            }
        }
    }

    fun log(event: AnalyticsEventJson) {
        if (!enabled) return
        scope.launch {
            mutex.withLock { queue.addLast(event) }
        }
    }

    suspend fun flush() {
        if (!enabled) return
        val a = api ?: return
        val batch = mutex.withLock {
            if (queue.isEmpty()) return
            val out = mutableListOf<AnalyticsEventJson>()
            repeat(minOf(50, queue.size)) { out.add(queue.removeFirst()) }
            out
        }
        if (batch.isEmpty()) return
        runCatching {
            a.postEvents(AnalyticsBatchJson(events = batch))
        }
    }
}
