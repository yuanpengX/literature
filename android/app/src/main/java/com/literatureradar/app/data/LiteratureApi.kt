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
    @GET(ApiV1Paths.FEED)
    suspend fun getFeed(
        @Query("cursor") cursor: String?,
        @Query("limit") limit: Int = 30,
        @Query("sort") sort: String = "recommended",
        /** arxiv / journal / conference；不传则服务端返回全部（如本地 Worker） */
        @Query("channel") channel: String? = null,
    ): FeedResponseJson

    @GET(ApiV1Paths.SEARCH)
    suspend fun search(
        @Query("q") q: String,
        /** 与小程序 search 默认一致 */
        @Query("limit") limit: Int = 40,
    ): SearchResponseJson

    @GET(ApiV1Paths.PAPER)
    suspend fun getPaper(@Path("id") id: Int): PaperJson

    @POST(ApiV1Paths.EVENTS)
    suspend fun postEvents(@Body body: AnalyticsBatchJson): Response<ResponseBody>

    @PUT(ApiV1Paths.USERS_ME_PREFERENCES)
    suspend fun putPreferences(@Body body: PreferencesBody): PreferencesOkJson

    @PUT(ApiV1Paths.USERS_ME_LLM)
    suspend fun putLlmCredentials(@Body body: UserLlmCredentialsBody): PreferencesOkJson

    @DELETE(ApiV1Paths.USERS_ME_LLM)
    suspend fun deleteLlmCredentials(): PreferencesOkJson

    @GET(ApiV1Paths.DAILY_PICKS_ME)
    suspend fun getDailyPicks(@Query("date") date: String? = null): DailyPicksResponseJson

    @POST(ApiV1Paths.DAILY_PICKS_ME_RUN)
    suspend fun runDailyPicksNow(): DailyPicksResponseJson

    @GET(ApiV1Paths.SUBSCRIPTIONS_CATALOG)
    suspend fun getSubscriptionCatalog(): SubscriptionCatalogJson

    @GET(ApiV1Paths.USERS_ME_SUBSCRIPTIONS)
    suspend fun getMySubscriptions(): UserSubscriptionsJson

    @PUT(ApiV1Paths.USERS_ME_SUBSCRIPTIONS)
    suspend fun putMySubscriptions(@Body body: UserSubscriptionsJson): UserSubscriptionsJson

    @GET(ApiV1Paths.USERS_ME_SUBSCRIPTIONS_FETCH_NOW)
    suspend fun requestSubscriptionFetch(
        /** arxiv | journal | conference：仅抓取该频道；省略则全量 */
        @Query("channel") channel: String? = null,
    ): PreferencesOkJson
}
