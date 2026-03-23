package com.literatureradar.app.data

import com.literatureradar.app.data.local.PaperEntity
import java.time.Instant
import java.time.format.DateTimeParseException

fun String?.toEpochMillis(): Long? {
    if (this.isNullOrBlank()) return null
    return try {
        Instant.parse(this).toEpochMilli()
    } catch (_: DateTimeParseException) {
        null
    }
}

fun PaperJson.toEntity(cachedAtMillis: Long = System.currentTimeMillis()): PaperEntity =
    PaperEntity(
        id = id,
        externalId = externalId,
        title = title,
        abstract = abstract,
        authorsText = authorsText,
        pdfUrl = pdfUrl,
        htmlUrl = htmlUrl,
        source = source,
        primaryCategory = primaryCategory,
        publishedAtIso = publishedAt,
        publishedAtMillis = publishedAt.toEpochMillis(),
        hotScore = hotScore,
        rankReason = rankReason,
        citationCount = citationCount,
        cachedAtMillis = cachedAtMillis,
    )

fun PaperEntity.toPaperJson(): PaperJson =
    PaperJson(
        id = id,
        externalId = externalId,
        title = title,
        abstract = abstract,
        authorsText = authorsText,
        pdfUrl = pdfUrl,
        htmlUrl = htmlUrl,
        source = source,
        primaryCategory = primaryCategory,
        publishedAt = publishedAtIso,
        hotScore = hotScore,
        rankReason = rankReason,
        rankTags = emptyList(),
        feedBlurb = "",
        citationCount = citationCount,
    )
