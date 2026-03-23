package com.literatureradar.app.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "papers")
data class PaperEntity(
    @PrimaryKey val id: Int,
    val externalId: String,
    val title: String,
    val abstract: String,
    val authorsText: String = "",
    val pdfUrl: String?,
    val htmlUrl: String?,
    val source: String,
    val primaryCategory: String?,
    val publishedAtIso: String?,
    val publishedAtMillis: Long?,
    val hotScore: Double,
    val rankReason: String?,
    val citationCount: Int = 0,
    val cachedAtMillis: Long,
)
