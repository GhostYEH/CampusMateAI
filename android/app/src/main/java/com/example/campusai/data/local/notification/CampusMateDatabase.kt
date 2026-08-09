package com.example.campusai.data.local.notification

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [RawNotificationEntity::class], version = 1, exportSchema = false)
abstract class CampusMateDatabase : RoomDatabase() {
    abstract fun rawNotificationDao(): RawNotificationDao

    companion object {
        const val DATABASE_NAME = "campusmate_notifications.db"

        fun create(context: Context): CampusMateDatabase = Room.databaseBuilder(
            context.applicationContext,
            CampusMateDatabase::class.java,
            DATABASE_NAME,
        ).build()
    }
}
