package com.example.campusai.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.campusai.data.model.CampusActivity
import com.example.campusai.data.model.CampusFile
import com.example.campusai.data.model.FavoriteItem
import com.example.campusai.data.model.PersonalHubSnapshot

import com.example.campusai.data.model.User
import com.example.campusai.data.news.CampusNewsPreferences
import com.example.campusai.BuildConfig
import com.example.campusai.data.notification.NotificationSource
import com.example.campusai.data.notification.NotificationSourceSettings
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import org.json.JSONArray
import org.json.JSONObject

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "campus_prefs")

class AppDataStore(private val context: Context) : PersonalHubDataSource, KeyValueStorage, CampusNewsPreferences {

    private val KEY_SESSION = stringPreferencesKey("campus_session")
    private val KEY_ACCESS_TOKEN = stringPreferencesKey("campus_access_token")
    private val KEY_REFRESH_TOKEN = stringPreferencesKey("campus_refresh_token")
    private val KEY_MOCK_MODE = booleanPreferencesKey("campus_mock_mode")
    private val KEY_REDUCE_MOTION = booleanPreferencesKey("campus_reduce_motion")
    private val KEY_DARK_MODE = booleanPreferencesKey("campus_dark_mode")
    private val KEY_REMINDERS = booleanPreferencesKey("campus_reminders")
    private val KEY_LEARNING_ASSISTANCE = booleanPreferencesKey("campus_learning_assistance")
    private val KEY_NOTIFICATION_WECHAT = booleanPreferencesKey("campus_notification_wechat")
    private val KEY_NOTIFICATION_XUEXITONG = booleanPreferencesKey("campus_notification_xuexitong")
    private val KEY_NOTIFICATION_QQ = booleanPreferencesKey("campus_notification_qq")
    private val KEY_NOTIFICATION_WECOM = booleanPreferencesKey("campus_notification_wecom")
    private val KEY_NOTIFICATION_OTHER = booleanPreferencesKey("campus_notification_other")
    private val KEY_CAMPUS_NEWS_READ_IDS = stringSetPreferencesKey("campus_news_read_ids")
    private val KEY_CAMPUS_NEWS_FAVORITE_IDS = stringSetPreferencesKey("campus_news_favorite_ids")

    override val campusNewsReadIds: Flow<Set<String>> = context.dataStore.data.map { prefs ->
        prefs[KEY_CAMPUS_NEWS_READ_IDS] ?: emptySet()
    }
    override val campusNewsFavoriteIds: Flow<Set<String>> = context.dataStore.data.map { prefs ->
        prefs[KEY_CAMPUS_NEWS_FAVORITE_IDS] ?: emptySet()
    }

    override suspend fun setCampusNewsReadIds(ids: Set<String>) {
        context.dataStore.edit { it[KEY_CAMPUS_NEWS_READ_IDS] = ids }
    }

    override suspend fun setCampusNewsFavoriteIds(ids: Set<String>) {
        context.dataStore.edit { it[KEY_CAMPUS_NEWS_FAVORITE_IDS] = ids }
    }

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

    suspend fun readAccessToken(): String? = context.dataStore.data
        .map { prefs: Preferences -> prefs[KEY_ACCESS_TOKEN] }
        .first()

    suspend fun readRefreshToken(): String? = context.dataStore.data
        .map { prefs: Preferences -> prefs[KEY_REFRESH_TOKEN] }
        .first()

    val mockMode: Flow<Boolean> = kotlinx.coroutines.flow.flowOf(false)

    val reduceMotion: Flow<Boolean> = context.dataStore.data.map { prefs: Preferences ->
        prefs[KEY_REDUCE_MOTION] ?: false
    }

    val darkMode: Flow<Boolean> = context.dataStore.data.map { it[KEY_DARK_MODE] ?: false }
    val remindersEnabled: Flow<Boolean> = context.dataStore.data.map { it[KEY_REMINDERS] ?: true }
    val learningAssistanceEnabled: Flow<Boolean> = context.dataStore.data.map {
        it[KEY_LEARNING_ASSISTANCE] ?: false
    }
    val notificationSourceSettings: Flow<NotificationSourceSettings> = context.dataStore.data.map { prefs ->
        NotificationSourceSettings(
            wechatEnabled = prefs[KEY_NOTIFICATION_WECHAT] ?: true,
            wecomEnabled = prefs[KEY_NOTIFICATION_WECOM] ?: true,
            xuexitongEnabled = prefs[KEY_NOTIFICATION_XUEXITONG] ?: true,
            qqEnabled = prefs[KEY_NOTIFICATION_QQ] ?: true,
            otherEnabled = prefs[KEY_NOTIFICATION_OTHER] ?: false,
        )
    }

    val pendingNotices: Flow<List<com.example.campusai.data.model.PendingNotice>> = context.dataStore.data.map { prefs ->
        val jsonStr = prefs[stringPreferencesKey("pending_notices")]
        if (jsonStr.isNullOrBlank()) {
            emptyList()
        } else {
            try {
                val array = JSONArray(jsonStr)
                List(array.length()) { i ->
                    val obj = array.getJSONObject(i)
                    com.example.campusai.data.model.PendingNotice(
                        id = obj.getString("id"),
                        content = obj.getString("content"),
                        sourceName = obj.getString("sourceName"),
                        publishedAt = obj.getString("publishedAt"),
                        retryCount = obj.optInt("retryCount", 0),
                        status = obj.optString("status", "pending")
                    )
                }
            } catch (e: Exception) {
                emptyList()
            }
        }
    }

    suspend fun savePendingNotices(notices: List<com.example.campusai.data.model.PendingNotice>) {
        context.dataStore.edit { prefs ->
            val array = JSONArray()
            notices.forEach { n ->
                val obj = JSONObject()
                obj.put("id", n.id)
                obj.put("content", n.content)
                obj.put("sourceName", n.sourceName)
                obj.put("publishedAt", n.publishedAt)
                obj.put("retryCount", n.retryCount)
                obj.put("status", n.status)
                array.put(obj)
            }
            prefs[stringPreferencesKey("pending_notices")] = array.toString()
        }
    }

    suspend fun enqueuePendingNotice(notice: com.example.campusai.data.model.PendingNotice) {
        context.dataStore.edit { prefs ->
            val key = stringPreferencesKey("pending_notices")
            val jsonStr = prefs[key]
            val array = if (jsonStr.isNullOrBlank()) JSONArray() else {
                try { JSONArray(jsonStr) } catch (e: Exception) { JSONArray() }
            }
            val obj = JSONObject()
            obj.put("id", notice.id)
            obj.put("content", notice.content)
            obj.put("sourceName", notice.sourceName)
            obj.put("publishedAt", notice.publishedAt)
            obj.put("retryCount", notice.retryCount)
            obj.put("status", notice.status)
            array.put(obj)
            prefs[key] = array.toString()
        }
    }

    suspend fun updateNoticeStatus(updatedNotices: List<com.example.campusai.data.model.PendingNotice>) {
        context.dataStore.edit { prefs ->
            val key = stringPreferencesKey("pending_notices")
            val jsonStr = prefs[key]
            if (jsonStr.isNullOrBlank()) return@edit
            val array = try { JSONArray(jsonStr) } catch (e: Exception) { JSONArray() }
            
            val updatedMap = updatedNotices.associateBy { it.id }
            val newArray = JSONArray()
            
            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                val id = obj.getString("id")
                if (updatedMap.containsKey(id)) {
                    val n = updatedMap[id]!!
                    val newObj = JSONObject()
                    newObj.put("id", n.id)
                    newObj.put("content", n.content)
                    newObj.put("sourceName", n.sourceName)
                    newObj.put("publishedAt", n.publishedAt)
                    newObj.put("retryCount", n.retryCount)
                    newObj.put("status", n.status)
                    newArray.put(newObj)
                } else {
                    newArray.put(obj)
                }
            }
            prefs[key] = newArray.toString()
        }
    }

    val monitoredGroupChats: Flow<Set<String>> = context.dataStore.data.map {
        it[stringSetPreferencesKey("monitored_group_chats")] ?: emptySet()
    }

    suspend fun addMonitoredGroupChat(groupName: String) {
        context.dataStore.edit {
            val current = it[stringSetPreferencesKey("monitored_group_chats")] ?: emptySet()
            it[stringSetPreferencesKey("monitored_group_chats")] = current + groupName
        }
    }

    suspend fun removeMonitoredGroupChat(groupName: String) {
        context.dataStore.edit {
            val current = it[stringSetPreferencesKey("monitored_group_chats")] ?: emptySet()
            it[stringSetPreferencesKey("monitored_group_chats")] = current - groupName
        }
    }

    val wecomGroupChats: Flow<Set<String>> = context.dataStore.data.map {
        it[stringSetPreferencesKey("wecom_group_chats")] ?: emptySet()
    }

    suspend fun addWecomGroupChat(groupName: String) {
        context.dataStore.edit {
            val current = it[stringSetPreferencesKey("wecom_group_chats")] ?: emptySet()
            it[stringSetPreferencesKey("wecom_group_chats")] = current + groupName
        }
    }

    suspend fun removeWecomGroupChat(groupName: String) {
        context.dataStore.edit {
            val current = it[stringSetPreferencesKey("wecom_group_chats")] ?: emptySet()
            it[stringSetPreferencesKey("wecom_group_chats")] = current - groupName
        }
    }

    val qqGroupChats: Flow<Set<String>> = context.dataStore.data.map {
        it[stringSetPreferencesKey("qq_group_chats")] ?: emptySet()
    }

    suspend fun addQqGroupChat(groupName: String) {
        context.dataStore.edit {
            val current = it[stringSetPreferencesKey("qq_group_chats")] ?: emptySet()
            it[stringSetPreferencesKey("qq_group_chats")] = current + groupName
        }
    }

    suspend fun removeQqGroupChat(groupName: String) {
        context.dataStore.edit {
            val current = it[stringSetPreferencesKey("qq_group_chats")] ?: emptySet()
            it[stringSetPreferencesKey("qq_group_chats")] = current - groupName
        }
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

    suspend fun setNotificationSourceEnabled(source: NotificationSource, enabled: Boolean) {
        context.dataStore.edit { prefs ->
            when (source) {
            NotificationSource.WECHAT -> prefs[KEY_NOTIFICATION_WECHAT] = enabled
            NotificationSource.WECOM -> prefs[KEY_NOTIFICATION_WECOM] = enabled
            NotificationSource.XUEXITONG -> prefs[KEY_NOTIFICATION_XUEXITONG] = enabled
                NotificationSource.QQ -> prefs[KEY_NOTIFICATION_QQ] = enabled
                NotificationSource.OTHER -> prefs[KEY_NOTIFICATION_OTHER] = enabled
            }
        }
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
