package com.literatureradar.app.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PaperDao {
    @Query(
        """
        SELECT * FROM papers 
        ORDER BY COALESCE(publishedAtMillis, cachedAtMillis) DESC 
        LIMIT :limit
        """,
    )
    suspend fun listRecent(limit: Int): List<PaperEntity>

    @Query("SELECT * FROM papers WHERE id = :id LIMIT 1")
    suspend fun getById(id: Int): PaperEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<PaperEntity>)
}
