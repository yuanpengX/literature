package com.literatureradar.app.data

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface LiteratureApi {
    @GET("api/v1/feed")
    suspend fun getFeed(
        @Query("cursor") cursor: String?,
        @Query("limit") limit: Int = 30,
        @Query("sort") sort: String = "recommended",
        /** arxiv / journal / conference；不传则服务端返回全部（如本地 Worker） */
        @Query("channel") channel: String? = null,
    ): FeedResponseJson

    @GET("api/v1/search")
    suspend fun search(
        @Query("q") q: String,
        @Query("limit") limit: Int = 30,
    ): SearchResponseJson

    @GET("api/v1/papers/{id}")
    suspend fun getPaper(@Path("id") id: Int): PaperJson

    @POST("api/v1/events")
    suspend fun postEvents(@Body body: AnalyticsBatchJson): Response<ResponseBody>

    @PUT("api/v1/users/me/preferences")
    suspend fun putPreferences(@Body body: PreferencesBody): PreferencesOkJson

    @PUT("api/v1/users/me/llm")
    suspend fun putLlmCredentials(@Body body: UserLlmCredentialsBody): PreferencesOkJson

    @DELETE("api/v1/users/me/llm")
    suspend fun deleteLlmCredentials(): PreferencesOkJson

    @GET("api/v1/daily-picks/me")
    suspend fun getDailyPicks(@Query("date") date: String? = null): DailyPicksResponseJson

    @POST("api/v1/daily-picks/me/run")
    suspend fun runDailyPicksNow(): DailyPicksResponseJson

    @GET("api/v1/subscriptions/catalog")
    suspend fun getSubscriptionCatalog(): SubscriptionCatalogJson

    @GET("api/v1/users/me/subscriptions")
    suspend fun getMySubscriptions(): UserSubscriptionsJson

    @PUT("api/v1/users/me/subscriptions")
    suspend fun putMySubscriptions(@Body body: UserSubscriptionsJson): UserSubscriptionsJson
}
