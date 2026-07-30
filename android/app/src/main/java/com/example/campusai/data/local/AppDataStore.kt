package com.example.campusai.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.campusai.data.model.User
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import org.json.JSONObject

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "campus_prefs")

class AppDataStore(private val context: Context) {

    private val KEY_SESSION = stringPreferencesKey("campus_session")
    private val KEY_ACCESS_TOKEN = stringPreferencesKey("campus_access_token")
    private val KEY_REFRESH_TOKEN = stringPreferencesKey("campus_refresh_token")
    private val KEY_MOCK_MODE = booleanPreferencesKey("campus_mock_mode")
    private val KEY_REDUCE_MOTION = booleanPreferencesKey("campus_reduce_motion")

    val session: Flow<User?> = context.dataStore.data.map { prefs ->
        prefs[KEY_SESSION]?.let { json: String ->
            try {
                val obj = JSONObject(json)
                User(
                    name = obj.optString("name", ""),
                    role = obj.optString("role", "student"),
                    detail = obj.optString("detail", "")
                )
            } catch (_: Exception) { null }
        }
    }

    val accessToken: Flow<String?> = context.dataStore.data.map { prefs: Preferences ->
        prefs[KEY_ACCESS_TOKEN]
    }

    val mockMode: Flow<Boolean> = context.dataStore.data.map { prefs: Preferences ->
        prefs[KEY_MOCK_MODE] ?: true
    }

    val reduceMotion: Flow<Boolean> = context.dataStore.data.map { prefs: Preferences ->
        prefs[KEY_REDUCE_MOTION] ?: false
    }

    suspend fun saveSession(user: User) {
        context.dataStore.edit { prefs ->
            val json = JSONObject()
            json.put("name", user.name)
            json.put("role", user.role)
            json.put("detail", user.detail)
            prefs[KEY_SESSION] = json.toString()
        }
    }

    suspend fun saveTokens(access: String?, refresh: String?) {
        context.dataStore.edit { prefs ->
            if (access != null) prefs[KEY_ACCESS_TOKEN] = access
            if (refresh != null) prefs[KEY_REFRESH_TOKEN] = refresh
        }
    }

    suspend fun clearSession() {
        context.dataStore.edit { prefs ->
            prefs.remove(KEY_SESSION)
            prefs.remove(KEY_ACCESS_TOKEN)
            prefs.remove(KEY_REFRESH_TOKEN)
        }
    }

    suspend fun setMockMode(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_MOCK_MODE] = enabled
        }
    }

    suspend fun setReduceMotion(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[KEY_REDUCE_MOTION] = enabled
        }
    }
}
