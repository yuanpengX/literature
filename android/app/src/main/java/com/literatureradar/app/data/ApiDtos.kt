package com.literatureradar.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class FeedResponseJson(
    val items: List<PaperJson> = emptyList(),
    @SerialName("next_cursor") val nextCursor: String? = null,
    /** 用户是否已在服务端配置 LLM；为 false 时推荐列表不返回条目 */
    @SerialName("blurbs_llm_ready") val blurbsLlmReady: Boolean = false,
    /** 同步窗口内未凑满 limit，后台仍在补全 blurb；宜下拉刷新 */
    @SerialName("blurbs_generation_incomplete") val blurbsGenerationIncomplete: Boolean = false,
)

@Serializable
data class SearchResponseJson(
    val items: List<PaperJson> = emptyList(),
)

@Serializable
data class PaperJson(
    val id: Int,
    @SerialName("external_id") val externalId: String,
    val title: String,
    val abstract: String,
    @SerialName("authors_text") val authorsText: String = "",
    @SerialName("pdf_url") val pdfUrl: String? = null,
    @SerialName("html_url") val htmlUrl: String? = null,
    val source: String,
    @SerialName("primary_category") val primaryCategory: String? = null,
    @SerialName("published_at") val publishedAt: String? = null,
    @SerialName("hot_score") val hotScore: Double = 0.0,
    @SerialName("rank_reason") val rankReason: String? = null,
    @SerialName("rank_tags") val rankTags: List<String> = emptyList(),
    @SerialName("feed_blurb") val feedBlurb: String = "",
    @SerialName("citation_count") val citationCount: Int = 0,
    /** 1～5：阅读价值星级（服务端按热度+相关性在列表内归一化） */
    @SerialName("read_value_stars") val readValueStars: Int = 3,
)

@Serializable
data class AnalyticsBatchJson(
    val events: List<AnalyticsEventJson> = emptyList(),
)

@Serializable
data class PreferencesBody(
    val keywords: String = "",
)

@Serializable
data class PreferencesOkJson(
    val ok: Boolean = true,
)

@Serializable
data class UserLlmCredentialsBody(
    @SerialName("base_url") val baseUrl: String,
    @SerialName("api_key") val apiKey: String,
    val model: String,
)

@Serializable
data class DailyPickItemJson(
    val paper: PaperJson,
    @SerialName("pick_blurb") val pickBlurb: String = "",
)

@Serializable
data class DailyPicksResponseJson(
    val date: String,
    val items: List<DailyPickItemJson> = emptyList(),
    val note: String? = null,
    val error: String? = null,
    @SerialName("server_llm_configured") val serverLlmConfigured: Boolean = false,
    /** 已启用订阅关键词，与订阅配置页及精选预筛一致 */
    @SerialName("subscription_keywords") val subscriptionKeywords: List<String> = emptyList(),
)

@Serializable
data class AnalyticsEventJson(
    @SerialName("event_type") val eventType: String,
    @SerialName("paper_id") val paperId: Int? = null,
    val surface: String? = null,
    val position: Int? = null,
    val payload: Map<String, String> = emptyMap(),
)

@Serializable
data class SubscriptionKeywordItemJson(
    val text: String,
    val enabled: Boolean = true,
)

@Serializable
data class SubscriptionJournalItemJson(
    val id: String,
    val enabled: Boolean = true,
    val name: String? = null,
    val rss: String? = null,
)

@Serializable
data class SubscriptionConferenceItemJson(
    val id: String,
    val enabled: Boolean = true,
    val name: String? = null,
    @SerialName("openalex_source_id") val openalexSourceId: String? = null,
)

@Serializable
data class JournalPresetJson(
    val id: String,
    val name: String,
    val abbr: String,
    val issn: String,
    val rss: String? = null,
)

@Serializable
data class ConferencePresetJson(
    val id: String,
    val name: String,
    val abbr: String,
    val note: String? = null,
    @SerialName("openalex_source_id") val openalexSourceId: String? = null,
)

@Serializable
data class SubscriptionCatalogJson(
    val journals: List<JournalPresetJson> = emptyList(),
    val conferences: List<ConferencePresetJson> = emptyList(),
    @SerialName("default_keywords") val defaultKeywords: List<SubscriptionKeywordItemJson> = emptyList(),
    @SerialName("default_journals") val defaultJournals: List<SubscriptionJournalItemJson> = emptyList(),
    @SerialName("default_conferences") val defaultConferences: List<SubscriptionConferenceItemJson> = emptyList(),
)

@Serializable
data class UserSubscriptionsJson(
    val keywords: List<SubscriptionKeywordItemJson> = emptyList(),
    val journals: List<SubscriptionJournalItemJson> = emptyList(),
    val conferences: List<SubscriptionConferenceItemJson> = emptyList(),
)

@Serializable
data class ClientConfigJson(
    @SerialName("http_ip_base") val httpIpBase: String = "",
)
