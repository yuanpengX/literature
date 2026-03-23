package com.literatureradar.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class FeedResponseJson(
    val items: List<PaperJson> = emptyList(),
    @SerialName("next_cursor") val nextCursor: String? = null,
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
    @SerialName("pdf_url") val pdfUrl: String? = null,
    @SerialName("html_url") val htmlUrl: String? = null,
    val source: String,
    @SerialName("primary_category") val primaryCategory: String? = null,
    @SerialName("published_at") val publishedAt: String? = null,
    @SerialName("hot_score") val hotScore: Double = 0.0,
    @SerialName("rank_reason") val rankReason: String? = null,
    @SerialName("citation_count") val citationCount: Int = 0,
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
data class DailyPicksResponseJson(
    val date: String,
    val items: List<PaperJson> = emptyList(),
    val note: String? = null,
    val error: String? = null,
    @SerialName("server_llm_configured") val serverLlmConfigured: Boolean = false,
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
