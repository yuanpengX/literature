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
    /** 与 API `feed_blurb` 对齐；供推荐列表一句话摘要缓存 */
    val feedBlurb: String = "",
    /** 与 API `read_value_stars` 对齐 */
    val readValueStars: Int = 3,
    val cachedAtMillis: Long,
)
