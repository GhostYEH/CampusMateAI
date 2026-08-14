package com.example.campusai.data.local.notification

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(entities = [RawNotificationEntity::class], version = 2, exportSchema = false)
abstract class CampusMateDatabase : RoomDatabase() {
    abstract fun rawNotificationDao(): RawNotificationDao

    companion object {
        const val DATABASE_NAME = "campusmate_notifications.db"

        @Volatile private var instance: CampusMateDatabase? = null

        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE raw_notifications ADD COLUMN attemptCount INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE raw_notifications ADD COLUMN stateUpdatedAt INTEGER NOT NULL DEFAULT 0")
                db.execSQL("UPDATE raw_notifications SET processingState = 'READY', stateUpdatedAt = capturedAt WHERE processingState = 'READY_FOR_REVIEW'")
            }
        }

        fun create(context: Context): CampusMateDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                CampusMateDatabase::class.java,
                DATABASE_NAME,
            ).addMigrations(MIGRATION_1_2).build().also { instance = it }
        }
    }
}
