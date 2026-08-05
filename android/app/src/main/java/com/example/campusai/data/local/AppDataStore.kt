package com.example.campusai.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.campusai.data.model.CampusActivity
import com.example.campusai.data.model.CampusFile
import com.example.campusai.data.model.FavoriteItem
import com.example.campusai.data.model.PersonalHubSnapshot
import com.example.campusai.data.model.User
import com.example.campusai.BuildConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import org.json.JSONArray
import org.json.JSONObject

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "campus_prefs")

class AppDataStore(private val context: Context) : PersonalHubDataSource, KeyValueStorage {

    private val KEY_SESSION = stringPreferencesKey("campus_session")
    private val KEY_ACCESS_TOKEN = stringPreferencesKey("campus_access_token")
    private val KEY_REFRESH_TOKEN = stringPreferencesKey("campus_refresh_token")
    private val KEY_MOCK_MODE = booleanPreferencesKey("campus_mock_mode")
    private val KEY_REDUCE_MOTION = booleanPreferencesKey("campus_reduce_motion")
    private val KEY_DARK_MODE = booleanPreferencesKey("campus_dark_mode")
    private val KEY_REMINDERS = booleanPreferencesKey("campus_reminders")
    private val KEY_LEARNING_ASSISTANCE = booleanPreferencesKey("campus_learning_assistance")

    val session: Flow<User?> = context.dataStore.data.map { prefs ->
        prefs[KEY_SESSION]?.let { json: String ->
            try {
                val obj = JSONObject(json)
                User(
                    name = obj.optString("name", ""),
                    role = obj.optString("role", "student"),
                    detail = obj.optString("detail", ""),
                    email = obj.optString("email", ""),
                    phone = obj.optString("phone", ""),
                    studentId = obj.optString("studentId", ""),
                    accountId = obj.optString("accountId", ""),
                )
            } catch (_: Exception) { null }
        }
    }

    val accessToken: Flow<String?> = context.dataStore.data.map { prefs: Preferences ->
        prefs[KEY_ACCESS_TOKEN]
    }

    val mockMode: Flow<Boolean> = context.dataStore.data.map { prefs: Preferences ->
        prefs[KEY_MOCK_MODE] ?: BuildConfig.DEFAULT_USE_MOCK
    }

    val reduceMotion: Flow<Boolean> = context.dataStore.data.map { prefs: Preferences ->
        prefs[KEY_REDUCE_MOTION] ?: false
    }

    val darkMode: Flow<Boolean> = context.dataStore.data.map { it[KEY_DARK_MODE] ?: false }
    val remindersEnabled: Flow<Boolean> = context.dataStore.data.map { it[KEY_REMINDERS] ?: true }
    val learningAssistanceEnabled: Flow<Boolean> = context.dataStore.data.map {
        it[KEY_LEARNING_ASSISTANCE] ?: false
    }

    suspend fun saveSession(user: User) {
        context.dataStore.edit { prefs ->
            val json = JSONObject()
            json.put("name", user.name)
            json.put("role", user.role)
            json.put("detail", user.detail)
            json.put("email", user.email)
            json.put("phone", user.phone)
            json.put("studentId", user.studentId)
            json.put("accountId", user.accountId)
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

    suspend fun setDarkMode(enabled: Boolean) {
        context.dataStore.edit { it[KEY_DARK_MODE] = enabled }
    }

    suspend fun setRemindersEnabled(enabled: Boolean) {
        context.dataStore.edit { it[KEY_REMINDERS] = enabled }
    }

    suspend fun setLearningAssistanceEnabled(enabled: Boolean) {
        context.dataStore.edit { it[KEY_LEARNING_ASSISTANCE] = enabled }
    }

    // ── 模块通用键值存储（KeyValueStorage） ──

    override fun observeRaw(key: String): Flow<String?> {
        val prefKey = stringPreferencesKey("campus_module_v1_$key")
        return context.dataStore.data.map { prefs -> prefs[prefKey] }
    }

    override suspend fun readRaw(key: String): String? {
        val prefKey = stringPreferencesKey("campus_module_v1_$key")
        return context.dataStore.data.map { prefs -> prefs[prefKey] }.first()
    }

    override suspend fun saveRaw(key: String, value: String) {
        val prefKey = stringPreferencesKey("campus_module_v1_$key")
        context.dataStore.edit { prefs -> prefs[prefKey] = value }
    }

    override fun observePersonalHub(accountKey: String): Flow<PersonalHubSnapshot?> {
        val key = stringPreferencesKey("campus_personal_hub_v1_$accountKey")
        return context.dataStore.data.map { prefs ->
            prefs[key]?.let(::decodePersonalHub)
        }
    }

    override suspend fun savePersonalHub(accountKey: String, snapshot: PersonalHubSnapshot) {
        val key = stringPreferencesKey("campus_personal_hub_v1_$accountKey")
        context.dataStore.edit { prefs ->
            prefs[key] = encodePersonalHub(snapshot)
        }
    }

    private fun encodePersonalHub(snapshot: PersonalHubSnapshot): String {
        val root = JSONObject()
        root.put("files", JSONArray().apply {
            snapshot.files.forEach { file ->
                put(JSONObject().apply {
                    put("id", file.id)
                    put("name", file.name)
                    put("category", file.category)
                    put("sizeLabel", file.sizeLabel)
                    put("updatedAt", file.updatedAt)
                    put("source", file.source)
                    put("isFavorite", file.isFavorite)
                })
            }
        })
        root.put("activities", JSONArray().apply {
            snapshot.activities.forEach { activity ->
                put(JSONObject().apply {
                    put("id", activity.id)
                    put("title", activity.title)
                    put("organizer", activity.organizer)
                    put("date", activity.date)
                    put("location", activity.location)
                    put("status", activity.status)
                    put("isFavorite", activity.isFavorite)
                })
            }
        })
        root.put("favorites", JSONArray().apply {
            snapshot.favorites.forEach { favorite ->
                put(JSONObject().apply {
                    put("id", favorite.id)
                    put("title", favorite.title)
                    put("type", favorite.type)
                    put("subtitle", favorite.subtitle)
                    put("savedAt", favorite.savedAt)
                    put("sourceRoute", favorite.sourceRoute)
                })
            }
        })
        return root.toString()
    }

    private fun decodePersonalHub(raw: String): PersonalHubSnapshot? = try {
        val root = JSONObject(raw)
        val filesJson = root.optJSONArray("files") ?: JSONArray()
        val activitiesJson = root.optJSONArray("activities") ?: JSONArray()
        val favoritesJson = root.optJSONArray("favorites") ?: JSONArray()
        PersonalHubSnapshot(
            files = List(filesJson.length()) { index ->
                filesJson.getJSONObject(index).let { obj ->
                    CampusFile(
                        // 兼容历史 Long id 与新 String id
                        id = obj.optString("id").ifBlank { obj.optLong("id").toString() },
                        name = obj.optString("name"),
                        category = obj.optString("category"),
                        sizeLabel = obj.optString("sizeLabel"),
                        updatedAt = obj.optString("updatedAt"),
                        source = obj.optString("source"),
                        isFavorite = obj.optBoolean("isFavorite"),
                    )
                }
            },
            activities = List(activitiesJson.length()) { index ->
                activitiesJson.getJSONObject(index).let { obj ->
                    CampusActivity(
                        id = obj.optString("id").ifBlank { obj.optLong("id").toString() },
                        title = obj.optString("title"),
                        organizer = obj.optString("organizer"),
                        date = obj.optString("date"),
                        location = obj.optString("location"),
                        status = obj.optString("status"),
                        isFavorite = obj.optBoolean("isFavorite"),
                    )
                }
            },
            favorites = List(favoritesJson.length()) { index ->
                favoritesJson.getJSONObject(index).let { obj ->
                    FavoriteItem(
                        id = obj.optString("id"),
                        title = obj.optString("title"),
                        type = obj.optString("type"),
                        subtitle = obj.optString("subtitle"),
                        savedAt = obj.optString("savedAt"),
                        sourceRoute = obj.optString("sourceRoute"),
                    )
                }
            },
        )
    } catch (_: Exception) {
        null
    }
}
