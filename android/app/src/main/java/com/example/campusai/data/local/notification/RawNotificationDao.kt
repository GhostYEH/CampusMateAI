package com.example.campusai.data.local.notification

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface RawNotificationDao {
    @Query("SELECT * FROM raw_notifications ORDER BY capturedAt DESC LIMIT :limit")
    fun observeRecent(limit: Int): Flow<List<RawNotificationEntity>>

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertIgnore(notification: RawNotificationEntity): Long

    @Query("SELECT * FROM raw_notifications WHERE processingState IN ('READY', 'RETRY') ORDER BY capturedAt ASC LIMIT :limit")
    suspend fun loadPending(limit: Int): List<RawNotificationEntity>

    @Query("UPDATE raw_notifications SET processingState = 'PROCESSING', stateUpdatedAt = :now WHERE id IN (:ids) AND processingState IN ('READY', 'RETRY')")
    suspend fun markProcessing(ids: List<Long>, now: Long): Int

    @Query("SELECT * FROM raw_notifications WHERE id IN (:ids) AND processingState = 'PROCESSING' ORDER BY capturedAt ASC")
    suspend fun loadProcessing(ids: List<Long>): List<RawNotificationEntity>

    @Transaction
    suspend fun claimPending(limit: Int, now: Long): List<RawNotificationEntity> {
        val candidates = loadPending(limit)
        if (candidates.isEmpty()) return emptyList()
        val ids = candidates.map { it.id }
        markProcessing(ids, now)
        return loadProcessing(ids)
    }

    @Query("UPDATE raw_notifications SET processingState = :state, attemptCount = attemptCount + :attemptIncrement, stateUpdatedAt = :now WHERE id IN (:ids)")
    suspend fun updateState(ids: List<Long>, state: String, attemptIncrement: Int, now: Long)

    @Query("UPDATE raw_notifications SET processingState = 'RETRY', stateUpdatedAt = :now WHERE processingState = 'PROCESSING' AND stateUpdatedAt < :staleBefore")
    suspend fun recoverStaleProcessing(staleBefore: Long, now: Long): Int

    @Query("SELECT COUNT(*) FROM raw_notifications WHERE processingState IN ('READY', 'RETRY')")
    suspend fun pendingCount(): Int

    @Query("DELETE FROM raw_notifications WHERE processingState IN ('COMPLETED', 'IGNORED') AND stateUpdatedAt < :before")
    suspend fun deleteCompletedBefore(before: Long): Int

    @Query("DELETE FROM raw_notifications WHERE processingState = 'FAILED' AND stateUpdatedAt < :before")
    suspend fun deleteFailedBefore(before: Long): Int

    @Query("DELETE FROM raw_notifications WHERE processingState IN ('COMPLETED', 'IGNORED', 'FAILED') AND id NOT IN (SELECT id FROM raw_notifications ORDER BY capturedAt DESC LIMIT :keepRecent)")
    suspend fun trimTerminalHistory(keepRecent: Int): Int

    @Query("DELETE FROM raw_notifications WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("DELETE FROM raw_notifications")
    suspend fun clear()
}
