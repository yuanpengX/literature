package com.literatureradar.app.notify

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.literatureradar.app.MainActivity
import com.literatureradar.app.R

object NotificationHelper {
    const val CHANNEL_ID = "literature_digest"
    private const val CHANNEL_NAME = "文献更新"
    private var channelCreated = false

    fun ensureChannel(ctx: Context) {
        if (channelCreated) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "定时检查是否有新论文"
            }
            (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(ch)
        }
        channelCreated = true
    }

    fun showNewPapersHint(ctx: Context, sampleTitle: String) {
        ensureChannel(ctx)
        val intent = android.content.Intent(ctx, MainActivity::class.java).apply {
            flags = android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = android.app.PendingIntent.getActivity(
            ctx,
            0,
            intent,
            android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE,
        )
        val n = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_popup_reminder)
            .setContentTitle("文献雷达")
            .setContentText("可能有新论文：$sampleTitle")
            .setStyle(NotificationCompat.BigTextStyle().bigText("可能有新论文，轻点打开应用查看推荐。\n\n$sampleTitle"))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(ctx).notify(1001, n)
    }
}
