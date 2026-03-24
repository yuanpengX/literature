package com.literatureradar.app

import android.app.Application
import android.content.Context.MODE_PRIVATE
import com.literatureradar.app.notify.NotificationHelper
import com.literatureradar.app.prefs.AppPrefs
import com.literatureradar.app.work.DigestScheduler

class LitApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        AppPrefs.applyHttpsDomainDefaultPolicyOnce(this)
        ServiceLocator.init(this)
        val on = getSharedPreferences("literature_prefs", MODE_PRIVATE)
            .getBoolean("analytics_on", true)
        ServiceLocator.analytics.setEnabled(on)
        NotificationHelper.ensureChannel(this)
        DigestScheduler.schedule(this)
    }
}
