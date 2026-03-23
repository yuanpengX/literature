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
data class AnalyticsEventJson(
    @SerialName("event_type") val eventType: String,
    @SerialName("paper_id") val paperId: Int? = null,
    val surface: String? = null,
    val position: Int? = null,
    val payload: Map<String, String> = emptyMap(),
)
