package com.example.campusai.data.local.notification

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface RawNotificationDao {
    @Query("SELECT * FROM raw_notifications ORDER BY capturedAt DESC LIMIT :limit")
    fun observeRecent(limit: Int): Flow<List<RawNotificationEntity>>

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertIgnore(notification: RawNotificationEntity): Long

    @Query("DELETE FROM raw_notifications WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("DELETE FROM raw_notifications")
    suspend fun clear()
}
