package com.literatureradar.app

import android.content.Context
import android.content.Context.MODE_PRIVATE
import androidx.room.Room
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.literatureradar.app.data.Analytics
import com.literatureradar.app.data.LiteratureApi
import com.literatureradar.app.data.local.AppDatabase
import com.literatureradar.app.data.llm.LlmClient
import com.literatureradar.app.data.llm.LlmSecureStore
import com.literatureradar.app.prefs.AppPrefs
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object ServiceLocator {
    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    private lateinit var appContext: Context

    lateinit var db: AppDatabase
        private set

    lateinit var llmStore: LlmSecureStore
        private set

    lateinit var llmClient: LlmClient
        private set

    /** 与 Retrofit 生命周期解耦，切换 Base URL 时仅 [bind] 新 API。 */
    val analytics: Analytics = Analytics()

    private data class NetworkBundle(
        val baseUrl: String,
        val api: LiteratureApi,
    )

    @Volatile
    private var network: NetworkBundle? = null

    val api: LiteratureApi
        get() = network?.api ?: error("ServiceLocator 未初始化")

    fun init(context: Context) {
        val app = context.applicationContext
        if (!::appContext.isInitialized) {
            appContext = app
            db = Room.databaseBuilder(app, AppDatabase::class.java, "literature.db")
                .addMigrations(
                    AppDatabase.MIGRATION_1_2,
                    AppDatabase.MIGRATION_2_3,
                    AppDatabase.MIGRATION_3_4,
                )
                .fallbackToDestructiveMigration()
                .build()
            llmStore = LlmSecureStore(app)
            llmClient = LlmClient(llmStore)
        }
        rebuildNetworkIfNeeded()
    }

    fun rebuildNetworkIfNeeded() {
        if (!::appContext.isInitialized) return
        val defaultBase = appContext.getString(R.string.api_base_url)
        val fromPrefs = AppPrefs.getApiBaseUrl(appContext).trim()
        val raw = (fromPrefs.ifBlank { defaultBase }).trim()
        val base = AppPrefs.normalizeApiBaseUrl(raw).trimEnd('/') + "/"
        val cur = network
        if (cur != null && cur.baseUrl == base) return

        val client = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val req = chain.request().newBuilder()
                    .header("X-User-Id", UserIdProvider.get(appContext))
                    .build()
                chain.proceed(req)
            }
            .build()
        val retrofit = Retrofit.Builder()
            .baseUrl(base)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
        val litApi = retrofit.create(LiteratureApi::class.java)
        analytics.bind(litApi)
        val allow = appContext.getSharedPreferences("literature_prefs", MODE_PRIVATE)
            .getBoolean("analytics_on", true)
        analytics.setEnabled(allow)
        network = NetworkBundle(base, litApi)
    }
}
