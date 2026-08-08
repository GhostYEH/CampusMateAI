package com.example.campusai.workers

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.chaoxingDataStore by preferencesDataStore(name = "chaoxing_sync_prefs")

class ChaoxingSyncStateStore(private val context: Context) {
    private val KEY_IS_CONNECTED = booleanPreferencesKey("chaoxing_is_connected")
    private val KEY_REAUTH_REQUIRED = booleanPreferencesKey("chaoxing_reauth_required")
    private val KEY_LAST_SYNCED_AT = stringPreferencesKey("chaoxing_last_synced_at")

    val isConnected: Flow<Boolean> = context.chaoxingDataStore.data.map { it[KEY_IS_CONNECTED] ?: false }
    val reauthRequired: Flow<Boolean> = context.chaoxingDataStore.data.map { it[KEY_REAUTH_REQUIRED] ?: false }
    val lastSyncedAt: Flow<String?> = context.chaoxingDataStore.data.map { it[KEY_LAST_SYNCED_AT] }

    suspend fun setConnected(connected: Boolean) {
        context.chaoxingDataStore.edit { it[KEY_IS_CONNECTED] = connected }
    }

    suspend fun setReauthRequired(required: Boolean) {
        context.chaoxingDataStore.edit { it[KEY_REAUTH_REQUIRED] = required }
    }

    suspend fun setLastSyncedAt(timestamp: String) {
        context.chaoxingDataStore.edit { it[KEY_LAST_SYNCED_AT] = timestamp }
    }
}
