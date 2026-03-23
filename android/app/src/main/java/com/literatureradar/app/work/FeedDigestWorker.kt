package com.literatureradar.app.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.literatureradar.app.ServiceLocator
import com.literatureradar.app.data.toEntity
import com.literatureradar.app.notify.NotificationHelper
import com.literatureradar.app.prefs.AppPrefs
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * 周期性拉取推荐流（按时间序），若列表顶部论文 id 变化则发**本地通知**。
 * 不依赖 FCM；与服务端推送可并存。
 */
class FeedDigestWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        if (!AppPrefs.isLocalDigestEnabled(applicationContext)) {
            return Result.success()
        }
        ServiceLocator.init(applicationContext)
        return try {
            val dao = ServiceLocator.db.paperDao()
            val res = ServiceLocator.api.getFeed(cursor = null, limit = 20, sort = "recent")
            val top = res.items.firstOrNull() ?: return Result.success()
            val last = AppPrefs.getLastFeedTopId(applicationContext)
            if (last != -1 && top.id != last) {
                NotificationHelper.showNewPapersHint(applicationContext, top.title)
            }
            AppPrefs.setLastFeedTopId(applicationContext, top.id)
            if (res.items.isNotEmpty()) {
                withContext(Dispatchers.IO) {
                    dao.upsertAll(res.items.map { it.toEntity() })
                }
            }
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
