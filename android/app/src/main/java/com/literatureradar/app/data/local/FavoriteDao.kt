package com.literatureradar.app.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface FavoriteDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: FavoriteEntity)

    @Query("DELETE FROM favorites WHERE paperId = :paperId")
    suspend fun deleteByPaperId(paperId: Int)

    @Query("SELECT COUNT(*) FROM favorites WHERE paperId = :paperId")
    suspend fun countFor(paperId: Int): Int

    @Query(
        """
        SELECT p.* FROM papers p
        INNER JOIN favorites f ON p.id = f.paperId
        ORDER BY f.savedAtMillis DESC
        """,
    )
    fun observeFavoritePapers(): Flow<List<PaperEntity>>
}
