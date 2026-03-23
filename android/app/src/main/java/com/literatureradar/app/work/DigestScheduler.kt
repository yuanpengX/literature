package com.literatureradar.app.work

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.literatureradar.app.prefs.AppPrefs
import java.util.concurrent.TimeUnit

object DigestScheduler {
    private const val UNIQUE = "feed_digest_local"

    fun schedule(context: Context) {
        val ctx = context.applicationContext
        if (!AppPrefs.isLocalDigestEnabled(ctx)) {
            WorkManager.getInstance(ctx).cancelUniqueWork(UNIQUE)
            return
        }
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val req = PeriodicWorkRequestBuilder<FeedDigestWorker>(4, TimeUnit.HOURS)
            .setConstraints(constraints)
            .build()
        WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
            UNIQUE,
            ExistingPeriodicWorkPolicy.UPDATE,
            req,
        )
    }
}
