package com.example.campusai.data.repository

import android.app.Application
import com.example.campusai.data.local.AppDataStore
import com.example.campusai.data.local.CredentialStore
import com.example.campusai.data.news.CampusNewsPreferences
import com.example.campusai.data.expression.ExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionSessionManager
import com.example.campusai.data.expression.CounselorExpressionPolicy
import com.example.campusai.data.expression.MockExpressionRecognitionService
import com.example.campusai.data.expression.RealExpressionRecognitionService
import com.example.campusai.data.model.*
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.LoginRequest
import com.example.campusai.data.remote.RefreshRequest
import com.example.campusai.data.remote.ChatRequest
import com.example.campusai.data.remote.ExpressionSignalRequest
import com.example.campusai.data.remote.NoticeExtractRequest
import com.example.campusai.data.remote.PersonalTaskCreateRequest
import com.example.campusai.data.remote.PersonalTaskUpdateRequest
import com.example.campusai.data.remote.ImportanceRankRequest
import com.example.campusai.data.remote.PersonalFileCreateRequest
import com.example.campusai.data.remote.FileFavoriteToggleRequest
import com.example.campusai.data.remote.FavoriteCreateRequest
import com.example.campusai.data.remote.CourseContentItemDto
import com.example.campusai.data.remote.CourseContentSummaryDto
import com.example.campusai.data.remote.HomeBannerDto
import com.example.campusai.BuildConfig
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject

class AppRepository(
    application: Application,
    campusNewsPreferences: CampusNewsPreferences? = null,
) {

    data class BackendStatus(
        val online: Boolean,
        val mode: String,
        val knowledgeDocuments: Int?,
        val indexReady: Boolean?,
        val error: String? = null,
    )

    private val application = application
    private val dataStore = AppDataStore(application)
    private val credentialStore = CredentialStore(application)
    private val newsPreferences = campusNewsPreferences ?: dataStore
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    @Volatile
    private var autoLoginAttempted = false
    private val campusNewsPreferencesMutex = Mutex()
    private val newsReadIdsReady = CompletableDeferred<Unit>()
    private val newsFavoriteIdsReady = CompletableDeferred<Unit>()

    private val _session = MutableStateFlow<User?>(null)
    val session: StateFlow<User?> = _session.asStateFlow()

    val accessToken: StateFlow<String?> = dataStore.accessToken.stateIn(
        scope,
        SharingStarted.Eagerly,
        null,
    )

    private val _backendOnline = MutableStateFlow(false)
    val backendOnline: StateFlow<Boolean> = _backendOnline.asStateFlow()

    private val _mockMode = MutableStateFlow(false)
    val mockMode: StateFlow<Boolean> = _mockMode.asStateFlow()

    private val _reduceMotion = MutableStateFlow(false)
    val reduceMotion: StateFlow<Boolean> = _reduceMotion.asStateFlow()

    private val _darkMode = MutableStateFlow(false)
    val darkMode: StateFlow<Boolean> = _darkMode.asStateFlow()

    private val _remindersEnabled = MutableStateFlow(true)
    val remindersEnabled: StateFlow<Boolean> = _remindersEnabled.asStateFlow()
    private val _learningAssistanceEnabled = MutableStateFlow(false)
    val learningAssistanceEnabled: StateFlow<Boolean> = _learningAssistanceEnabled.asStateFlow()

    /** The only owner of the expression model and camera session in the app. */
    val expressionSessionManager = ExpressionSessionManager(
        application = application,
        createService = { useMock -> createExpressionRecognitionService(useMock) },
        initialUseMock = BuildConfig.DEFAULT_USE_MOCK,
    )


    private val taskMutex = Mutex()
    private var taskJob: Job? = null
    private val _tasks = MutableStateFlow<List<Task>>(emptyList())
    val tasks: StateFlow<List<Task>> = _tasks.asStateFlow()
    private val _taskError = MutableStateFlow<String?>(null)
    val taskError: StateFlow<String?> = _taskError.asStateFlow()

    val pendingCount: StateFlow<Int> = _tasks
        .map { list -> list.count { !it.done } }
        .stateIn(scope, SharingStarted.Eagerly, 0)

    private val _notices = MutableStateFlow(defaultNotices())
    val notices: StateFlow<List<Notice>> = _notices.asStateFlow()

    private val _campusNews = MutableStateFlow(defaultCampusNews())
    val campusNews: StateFlow<List<CampusNews>> = _campusNews.asStateFlow()

    private val _newsReadIds = MutableStateFlow<Set<String>>(emptySet())
    val newsReadIds: StateFlow<Set<String>> = _newsReadIds.asStateFlow()
    private val _newsFavoriteIds = MutableStateFlow<Set<String>>(emptySet())
    val newsFavoriteIds: StateFlow<Set<String>> = _newsFavoriteIds.asStateFlow()

    fun getCampusNewsById(id: String): CampusNews? = _campusNews.value.find { it.id == id }

    private val _courses = MutableStateFlow(defaultCourses())
    val courses: StateFlow<List<Course>> = _courses.asStateFlow()

    private val _homeBanners = MutableStateFlow<List<HomeBanner>>(emptyList())
    val homeBanners: StateFlow<List<HomeBanner>> = _homeBanners.asStateFlow()

    private val personalHubMutex = Mutex()
    private var personalHubJob: Job? = null
    private var activeAccountKey: String? = null
    private val personalHubMigratedAccountKeys = mutableSetOf<String>()

    private val _files = MutableStateFlow<List<CampusFile>>(emptyList())
    val files: StateFlow<List<CampusFile>> = _files.asStateFlow()

    private val _favorites = MutableStateFlow<List<FavoriteItem>>(emptyList())
    val favorites: StateFlow<List<FavoriteItem>> = _favorites.asStateFlow()

    private val _personalHubLoading = MutableStateFlow(false)
    val personalHubLoading: StateFlow<Boolean> = _personalHubLoading.asStateFlow()

    private val demos = mapOf(
        "student_demo" to User("林知夏", "student", "计算机科学与技术 · 大三", "lin.zhixia@campus.edu.cn", "138 0000 2026", "2024020318"),
    )

    init {
        // 注入 token 刷新回调：OkHttp Authenticator 在 401 时调用，自动用 refresh_token 换新 access_token，
        // 避免用户在 access_token 过期（后端默认 30 分钟）时看到「登录已失效」。
        ApiClient.setTokenRefresher {
            runBlocking { refreshAccessToken() }
        }
        scope.launch { dataStore.session.collect { stored ->
                // Session and token are persisted separately. Do not expose a
                // restored user until the bearer token has been restored too;
                // otherwise protected screens can race ahead and issue 401s.
                val token = dataStore.readAccessToken()
                ApiClient.setToken(token)
                if (stored == null) {
                    // 无持久化会话：尝试用「记住的账号密码」自动登录（仅尝试一次）
                    if (!autoLoginAttempted) {
                        autoLoginAttempted = true
                        tryAutoLoginWithSavedCredentials()
                    }
                    return@collect
                }
                // 有会话但 token 缺失或已过期：先尝试 refresh，再退回自动登录兜底
                if (token.isNullOrBlank() || isTokenExpired(token)) {
                    val refreshed = refreshAccessToken()
                    if (refreshed == null) {
                        if (!autoLoginAttempted) {
                            autoLoginAttempted = true
                            tryAutoLoginWithSavedCredentials()
                        }
                        if (_session.value == null) {
                            dataStore.clearSession()
                            _session.value = null
                            bindPersonalHub(null)
                            bindTasks(null)
                        }
                        return@collect
                    }
                    // refresh 成功，access_token 已更新到 ApiClient 与 DataStore
                }
                val defaults = stored.let { user ->
                    demos.values.firstOrNull { it.name == user.name && it.role == user.role }
                }
                val hydrated = if (defaults != null) {
                    stored.copy(
                        detail = if (
                            stored.name == "林知夏" &&
                            stored.detail in setOf("计算机学院 · 大二", "计算机学院·大二")
                        ) defaults.detail else stored.detail,
                        email = stored.email.ifBlank { defaults.email },
                        phone = stored.phone.ifBlank { defaults.phone },
                        studentId = stored.studentId.ifBlank { defaults.studentId },
                    )
                } else stored
                _session.value = hydrated
                if (hydrated != null && hydrated != stored) dataStore.saveSession(hydrated)
                bindPersonalHub(hydrated)
                bindTasks(hydrated)
            }
        }
        scope.launch {
            // Mock mode is strictly disabled
            _mockMode.value = false
            expressionSessionManager.setUseMock(false)
        }
        // A restored session does not pass through login(), so the old app left
        // backendOnline at its default false value until Settings was opened.
        // Keep one app-wide source of truth and refresh it as soon as the
        // repository is created.
        scope.launch { refreshBackendStatus() }
        scope.launch { loadCachedHomeBanners() }
        scope.launch { dataStore.reduceMotion.collect { _reduceMotion.value = it } }
        scope.launch { dataStore.darkMode.collect { _darkMode.value = it } }
        scope.launch { dataStore.remindersEnabled.collect { _remindersEnabled.value = it } }
        scope.launch { dataStore.learningAssistanceEnabled.collect { _learningAssistanceEnabled.value = it } }
        scope.launch {
            newsPreferences.campusNewsReadIds.collect {
                _newsReadIds.value = it
                newsReadIdsReady.complete(Unit)
            }
        }
        scope.launch {
            newsPreferences.campusNewsFavoriteIds.collect {
                _newsFavoriteIds.value = it
                newsFavoriteIdsReady.complete(Unit)
            }
        }
    }

    suspend fun markCampusNewsRead(newsId: String) = campusNewsPreferencesMutex.withLock {
        newsReadIdsReady.await()
        val ids = _newsReadIds.value
        if (newsId !in ids) {
            val updatedIds = ids + newsId
            newsPreferences.setCampusNewsReadIds(updatedIds)
            _newsReadIds.value = updatedIds
        }
    }

    suspend fun toggleCampusNewsFavorite(newsId: String) = campusNewsPreferencesMutex.withLock {
        newsFavoriteIdsReady.await()
        val ids = _newsFavoriteIds.value
        val updatedIds =
            if (newsId in ids) ids - newsId else ids + newsId
        newsPreferences.setCampusNewsFavoriteIds(updatedIds)
        _newsFavoriteIds.value = updatedIds
    }

    suspend fun login(username: String, password: String, rememberCredentials: Boolean = false): User {
        _backendOnline.value = ApiClient.probeBackend()
        val user: User
        if (_backendOnline.value) {
            val loginResp = ApiClient.api.login(LoginRequest(username, password))
            if (!loginResp.isSuccessful) throw Exception("账号或密码不正确")
            val body = loginResp.body()!!
            ApiClient.setToken(body.access_token)
            dataStore.saveTokens(body.access_token, body.refresh_token)
            val meResp = ApiClient.api.me()
            val meUser = meResp.body()?.user
            val displayName = meUser?.display_name?.takeIf { it.isNotBlank() }
                ?: meUser?.username?.takeIf { it.isNotBlank() }
                ?: username
            val detail = listOfNotNull(
                meUser?.college?.takeIf { it.isNotBlank() },
                meUser?.major?.takeIf { it.isNotBlank() },
                meUser?.grade?.takeIf { it.isNotBlank() },
            ).joinToString(" · ")
            user = User(
                name = displayName,
                role = meUser?.role?.takeIf { it.isNotBlank() } ?: "student",
                detail = detail,
                accountId = meUser?.id.orEmpty(),
                universityId = meUser?.university_id.orEmpty(),
            )
        } else {
            throw Exception("无法连接到后端服务器，请检查网络或后端是否运行")
        }
        _session.value = user
        dataStore.saveSession(user)
        if (rememberCredentials) {
            credentialStore.save(username.trim(), password)
        }
        return user
    }

    suspend fun loginChaoxing(username: String, password: String): Pair<Boolean, String> {
        return try {
            val req = com.example.campusai.data.remote.ChaoxingLoginRequest(username, password)
            val resp = ApiClient.chaoxingApi.loginChaoxing(req)
            if (resp.isSuccessful) {
                Pair(true, "")
            } else {
                val errorStr = resp.errorBody()?.string() ?: ""
                val msg = if (resp.code() == 403 || errorStr.contains("verification_required")) "verification_required" else "登录失败: ${resp.code()}"
                Pair(false, msg)
            }
        } catch (e: Exception) {
            Pair(false, "网络错误: ${e.message}")
        }
    }

    suspend fun syncChaoxing(): Pair<Boolean, String> {
        return try {
            val resp = ApiClient.chaoxingApi.syncChaoxing()
            if (resp.isSuccessful) {
                Pair(true, "")
            } else {
                val errorStr = resp.errorBody()?.string() ?: ""
                if (resp.code() == 401 || errorStr.contains("reauth_required") || resp.code() == 403 || errorStr.contains("verification_required")) {
                    Pair(false, if (errorStr.contains("verification_required") || resp.code() == 403) "verification_required" else "reauth_required")
                } else {
                    Pair(false, "同步失败: ${resp.code()}")
                }
            }
        } catch (e: Exception) {
            Pair(false, "网络错误: ${e.message}")
        }
    }

    suspend fun getChaoxingStatus(): com.example.campusai.data.remote.ChaoxingSyncStatusResponse? {
        return try {
            val resp = ApiClient.chaoxingApi.getChaoxingStatus()
            if (resp.isSuccessful) {
                resp.body()
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    suspend fun disconnectChaoxing(): Boolean {
        return try {
            val resp = ApiClient.api.disconnectChaoxing()
            resp.isSuccessful
        } catch (e: Exception) {
            false
        }
    }

    suspend fun logout() {
        _session.value = null
        ApiClient.setToken(null)
        dataStore.clearSession()
        // 主动退出登录：清除记住的账号密码，避免下次打开又自动登录
        credentialStore.clear()
        autoLoginAttempted = false
    }

    /**
     * 用 refresh_token 换取新的 access_token。成功返回新 access_token 并更新内存与持久化，
     * 失败返回 null（由调用方决定是否退回自动登录或登出）。
     */
    suspend fun refreshAccessToken(): String? {
        val refreshToken = dataStore.readRefreshToken()
        if (refreshToken.isNullOrBlank()) return null
        return try {
            val resp = ApiClient.authApi.refresh(RefreshRequest(refreshToken))
            if (!resp.isSuccessful) return null
            val body = resp.body() ?: return null
            ApiClient.setToken(body.access_token)
            dataStore.saveTokens(body.access_token, body.refresh_token)
            body.access_token
        } catch (_: Exception) {
            null
        }
    }

    /** 解析 JWT 的 exp 判断是否已过期（提前 30 秒判定，避免边界 401）。无法解析时不判定过期。 */
    private fun isTokenExpired(token: String?): Boolean {
        if (token.isNullOrBlank()) return true
        return try {
            val parts = token.split(".")
            if (parts.size < 2) return false
            val payload = java.util.Base64.getUrlDecoder().decode(parts[1])
            val exp = JSONObject(String(payload)).optLong("exp", 0L)
            if (exp <= 0L) return false
            System.currentTimeMillis() / 1000 >= exp - 30
        } catch (_: Exception) {
            false
        }
    }

    /** 用「记住的账号密码」自动登录。失败（后端未启动/密码已改等）则静默保持未登录态。 */
    private suspend fun tryAutoLoginWithSavedCredentials() {
        val cred = credentialStore.load() ?: return
        try {
            login(cred.username, cred.password, rememberCredentials = true)
        } catch (_: Exception) {
            // 自动登录失败，保持未登录，等用户手动登录
        }
    }

    /** 读取「记住的账号密码」中的用户名，供登录页预填。 */
    suspend fun savedUsername(): String? = credentialStore.savedUsername()

    suspend fun refreshBackendStatus(): BackendStatus {
        return try {
            val health = ApiClient.api.health()
            val knowledge = ApiClient.api.knowledgeStatus()
            val online = health.isSuccessful
            _backendOnline.value = online
            if (online && _session.value != null) {
                // The task tab may have loaded before this initial health check.
                // Refresh it now so a stale offline banner cannot survive a
                // successful connection.
                refreshTasks()
            }
            BackendStatus(
                online = online,
                mode = health.body()?.mode ?: (if (online) "Real" else "Error ${health.code()}"),
                knowledgeDocuments = knowledge.body()?.document_count,
                indexReady = knowledge.body()?.index_ready,
                error = if (online) null else "健康检查返回 ${health.code()}",
            )
        } catch (error: Exception) {
            _backendOnline.value = false
            BackendStatus(false, "连接失败: ${error.message ?: "未知错误"}", null, null, error.message ?: "无法连接后端")
        }
    }

    // ===== 后端数据拉取（离线/Mock 时回退本地） =====

    /** 拉取校园通知（聚合学生可见班级的已发布通知）。 */
    suspend fun refreshNotices() {
        if (!_backendOnline.value || _mockMode.value) return
        try {
            val resp = ApiClient.api.listNotices(page = 1, pageSize = 50)
            if (resp.isSuccessful) {
                val items = resp.body()?.items.orEmpty()
                if (items.isNotEmpty()) {
                    _notices.value = items.map { dto ->
                        Notice(
                            id = dto.id,
                            title = dto.title,
                            source = dto.source.orEmpty(),
                            time = dto.time.orEmpty(),
                            unread = dto.unread,
                            category = dto.category.orEmpty(),
                            content = dto.content.orEmpty(),
                        )
                    }
                }
            }
        } catch (_: Exception) { /* 保留现有数据 */ }
    }

    /** 拉取校园热搜（来自校园论坛的热门帖子）。 */
    suspend fun refreshCampusNews(): Boolean {
        if (!_backendOnline.value || _mockMode.value) return true
        return try {
            val resp = ApiClient.api.listCommunityPosts(sort = "hot", page = 1, pageSize = 50)
            if (!resp.isSuccessful) {
                false
            } else {
                val items = resp.body()?.items.orEmpty()
                _campusNews.value = items.map { dto ->
                    CampusNews(
                        id = dto.id,
                        title = dto.title,
                        summary = dto.content,
                        content = dto.content,
                        source = dto.author_name,
                        time = dto.created_at,
                        category = dto.category,
                        tags = listOf("热度 ${dto.like_count + dto.comment_count}"),
                        relatedTasks = emptyList(),
                    )
                }
                true
            }
        } catch (_: Exception) {
            false
        }
    }

    /** 拉取课程列表。 */
    suspend fun refreshHomeBanners() {
        try {
            val response = ApiClient.api.homeBanners()
            if (response.isSuccessful) {
                val banners = response.body()?.items.orEmpty().map(::mapHomeBanner)
                _homeBanners.value = banners
                dataStore.saveRaw(HOME_BANNER_CACHE_KEY, encodeHomeBanners(banners))
            }
        } catch (_: Exception) {
            // Keep the last successful backend snapshot.
        }
    }

    private suspend fun loadCachedHomeBanners() {
        val raw = dataStore.readRaw(HOME_BANNER_CACHE_KEY) ?: return
        try {
            val array = JSONArray(raw)
            _homeBanners.value = List(array.length()) { index ->
                val item = array.getJSONObject(index)
                HomeBanner(
                    id = item.getString("id"),
                    eyebrow = item.getString("eyebrow"),
                    title = item.getString("title"),
                    subtitle = item.getString("subtitle"),
                    ctaLabel = item.getString("ctaLabel"),
                    imageUrl = item.getString("imageUrl"),
                    actionKey = item.getString("actionKey"),
                    themeKey = item.getString("themeKey"),
                    sortOrder = item.optInt("sortOrder", 0),
                    status = item.optString("status", "PUBLISHED"),
                    startsAt = item.optString("startsAt").takeIf { !item.isNull("startsAt") && it.isNotBlank() },
                    endsAt = item.optString("endsAt").takeIf { !item.isNull("endsAt") && it.isNotBlank() },
                    createdAt = item.optString("createdAt"),
                    updatedAt = item.optString("updatedAt"),
                )
            }
        } catch (_: Exception) {
            // Ignore an obsolete or malformed local snapshot.
        }
    }

    private fun mapHomeBanner(dto: HomeBannerDto) = HomeBanner(
        id = dto.id,
        eyebrow = dto.eyebrow,
        title = dto.title,
        subtitle = dto.subtitle,
        ctaLabel = dto.cta_label,
        imageUrl = ApiClient.resolveStaticUrl(dto.image_url).orEmpty(),
        actionKey = dto.action_key,
        themeKey = dto.theme_key,
        sortOrder = dto.sort_order,
        status = dto.status,
        startsAt = dto.starts_at,
        endsAt = dto.ends_at,
        createdAt = dto.created_at,
        updatedAt = dto.updated_at,
    )

    private fun encodeHomeBanners(items: List<HomeBanner>): String = JSONArray().apply {
        items.forEach { banner ->
            put(JSONObject().apply {
                put("id", banner.id)
                put("eyebrow", banner.eyebrow)
                put("title", banner.title)
                put("subtitle", banner.subtitle)
                put("ctaLabel", banner.ctaLabel)
                put("imageUrl", banner.imageUrl)
                put("actionKey", banner.actionKey)
                put("themeKey", banner.themeKey)
                put("sortOrder", banner.sortOrder)
                put("status", banner.status)
                put("startsAt", banner.startsAt)
                put("endsAt", banner.endsAt)
                put("createdAt", banner.createdAt)
                put("updatedAt", banner.updatedAt)
            })
        }
    }.toString()

    suspend fun refreshCourses() {
        if (!_backendOnline.value || _mockMode.value) return
        try {
            val resp = ApiClient.api.listCourses(page = 1, pageSize = 100)
            if (resp.isSuccessful) {
                val items = resp.body()?.items.orEmpty()
                if (items.isNotEmpty()) {
                    _courses.value = items.map { dto ->
                        Course(
                            id = dto.id,
                            name = dto.name,
                            code = dto.code ?: "",
                            type = dto.semester ?: "本学期",
                            teacher = dto.teacher_name ?: "待定",
                            location = dto.description ?: "",
                            provider = dto.provider,
                            external_id = dto.external_id,
                            source_url = dto.source_url,
                            last_synced_at = dto.last_synced_at,
                        )
                    }
                }
            }
        } catch (_: Exception) { /* 保留现有数据 */ }
    }

    private companion object {
        const val HOME_BANNER_CACHE_KEY = "home_banners_v1"
    }

    /** 拉取云端任务并合并到本地缓存。 */
    suspend fun refreshTasks() = taskMutex.withLock {
        if (!_backendOnline.value || _mockMode.value) {
            _taskError.value = if (_tasks.value.isEmpty()) {
                "待办需要连接真实后端后才能使用"
            } else {
                "暂时无法刷新，正在显示上次加载的待办"
            }
            return@withLock
        }
        try {
            val resp = ApiClient.api.listTasks(page = 1, pageSize = 200)
            if (resp.isSuccessful) {
                val items = resp.body()?.items.orEmpty()
                _tasks.value = TaskRemotePolicy.replaceAfterSuccessfulRead(_tasks.value, items.map { dto ->
                        Task(
                            id = dto.id,
                            title = dto.title,
                            due = dto.deadline ?: "待设置",
                            course = dto.source_name ?: "个人待办",
                            done = dto.status == "completed",
                            description = dto.description ?: dto.source_text ?: "",
                            importance = dto.importance ?: "unknown",
                        )
                    })
                _taskError.value = null
            } else {
                _taskError.value = if (resp.code() == 401) {
                    "登录已失效，请重新登录后同步待办"
                } else {
                    "待办数据加载失败，请稍后重试"
                }
            }
        } catch (_: Exception) {
            // Keep the current snapshot. A transient refresh failure must not blank
            // the screen or race a successful add/update operation.
            _taskError.value = "待办数据加载失败，请稍后重试"
        }
    }

    /** 批量评定任务重要程度（AI 优先 + 规则降级），评定后刷新本地缓存。 */
    suspend fun rankTaskImportance(taskIds: List<String> = emptyList()) {
        if (!_backendOnline.value || _mockMode.value) return
        try {
            val resp = ApiClient.api.rankTaskImportance(ImportanceRankRequest(task_ids = taskIds.takeIf { it.isNotEmpty() }))
            if (resp.isSuccessful) refreshTasks()
        } catch (_: Exception) { }
    }

    suspend fun loadCourseContent(courseId: String): Pair<CourseContentSummaryDto?, List<CourseContentItemDto>> {
        if (!_backendOnline.value || _mockMode.value || courseId.isBlank()) return null to emptyList()
        val summary = ApiClient.api.getCourseContentSummary(courseId)
        val content = ApiClient.api.getCourseContent(courseId, pageSize = 500)
        if (!content.isSuccessful) throw IllegalStateException("course_content_load_failed_${content.code()}")
        return summary.body() to content.body()?.items.orEmpty()
    }

    suspend fun syncCourseContent(courseId: String): Pair<CourseContentSummaryDto?, List<CourseContentItemDto>> {
        val response = ApiClient.api.syncCourseContent(courseId)
        if (!response.isSuccessful) throw IllegalStateException("course_content_sync_failed_${response.code()}")
        return loadCourseContent(courseId)
    }

    suspend fun getCourseResourceUrl(courseId: String, itemId: String): String? {
        val response = ApiClient.api.openCourseResource(courseId, itemId)
        if (!response.isSuccessful) return null
        return response.body()?.url
    }

    suspend fun downloadCourseResource(courseId: String, item: CourseContentItemDto): File? {
        val response = ApiClient.chaoxingApi.downloadCourseResource(courseId, item.id)
        val body = response.body()
        if (!response.isSuccessful || body == null) return null
        val safeName = item.title.replace(Regex("[\\\\/:*?\"<>|]"), "_").ifBlank { item.id }
        val targetDir = File(application.cacheDir, "chaoxing-resources").apply { mkdirs() }
        val target = File(targetDir, safeName.take(160))
        body.byteStream().use { input -> target.outputStream().use { output -> input.copyTo(output) } }
        return target
    }

    /** 拉取个人中心数据（文件 / 收藏 / 活动）。 */
    suspend fun refreshPersonalHub() {
        if (!_backendOnline.value || _mockMode.value) return
        try {
            val filesResp = ApiClient.api.listFiles()
            if (filesResp.isSuccessful) {
                val dtos = filesResp.body().orEmpty()
                _files.value = dtos.map { dto ->
                    CampusFile(
                        id = dto.id,
                        name = dto.name,
                        category = dto.category ?: "",
                        sizeLabel = dto.size_label ?: "",
                        updatedAt = dto.updated_at ?: "",
                        source = dto.source ?: "",
                        isFavorite = dto.is_favorite,
                    )
                }
            }
            val favResp = ApiClient.api.listFavorites()
            if (favResp.isSuccessful) {
                val dtos = favResp.body().orEmpty()
                _favorites.value = dtos.map { dto ->
                    FavoriteItem(
                        id = dto.id,
                        title = dto.title,
                        type = dto.type ?: "收藏",
                        subtitle = dto.subtitle ?: "",
                        savedAt = dto.saved_at ?: "",
                        sourceRoute = dto.source_route ?: "",
                    )
                }
            }
            persistPersonalHub()
        } catch (_: Exception) { /* 保留现有数据 */ }
    }

    suspend fun toggleTask(id: String) = taskMutex.withLock {
        val list = _tasks.value.toMutableList()
        val idx = list.indexOfFirst { it.id == id }
        if (idx >= 0) {
            val current = list[idx]
            val newDone = !current.done
            // 后端在线时同步状态机
            if (_backendOnline.value && !_mockMode.value && !id.startsWith("local_")) {
                try {
                    val resp = if (newDone) ApiClient.api.completeTask(id)
                    else ApiClient.api.restoreTask(id)
                    if (resp.isSuccessful) {
                        val dto = resp.body()
                        list[idx] = list[idx].copy(
                            done = dto?.status == "completed",
                            title = dto?.title ?: current.title,
                            due = dto?.deadline ?: current.due,
                            course = dto?.source_name ?: current.course,
                            description = dto?.description ?: current.description,
                        )
                        _tasks.value = list
                        return@withLock
                    }
                } catch (_: Exception) { /* 落入本地回退 */ }
            }
            return@withLock
        }
    }

    suspend fun addTask(title: String, due: String = "待设置", course: String = "个人待办", description: String = "") = taskMutex.withLock {
        if (_backendOnline.value && !_mockMode.value) {
            try {
                val resp = ApiClient.api.createTask(
                    PersonalTaskCreateRequest(
                        title = title,
                        description = description.ifBlank { null },
                        deadline = due.takeIf { it.isNotBlank() && it != "待设置" },
                        source_name = course.takeIf { it != "个人待办" },
                    )
                )
                if (resp.isSuccessful) {
                    val dto = resp.body() ?: return@withLock
                    val newTask = Task(
                        id = dto.id,
                        title = dto.title,
                        due = dto.deadline ?: "待设置",
                        course = dto.source_name ?: "个人待办",
                        done = dto.status == "completed",
                        description = dto.description ?: "",
                    )
                    _tasks.value = listOf(newTask) + _tasks.value
                    return@withLock
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        return@withLock
    }

    suspend fun deleteTask(id: String) = taskMutex.withLock {
        if (_backendOnline.value && !_mockMode.value && !id.startsWith("local_")) {
            try {
                val resp = ApiClient.api.deleteTask(id)
                if (resp.isSuccessful) {
                    _tasks.value = _tasks.value.filter { it.id != id }
                    return@withLock
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        return@withLock
    }

    fun getTaskById(id: String): Task? = _tasks.value.find { it.id == id }

    suspend fun updateTask(id: String, title: String, due: String, course: String, description: String) = taskMutex.withLock {
        if (_backendOnline.value && !_mockMode.value && !id.startsWith("local_")) {
            try {
                val resp = ApiClient.api.updateTask(
                    id,
                    PersonalTaskUpdateRequest(
                        title = title,
                        description = description.ifBlank { null },
                        deadline = due.takeIf { it.isNotBlank() && it != "待设置" },
                        source_name = course.takeIf { it != "个人待办" },
                    )
                )
                if (resp.isSuccessful) {
                    val dto = resp.body()
                    val list = _tasks.value.toMutableList()
                    val idx = list.indexOfFirst { it.id == id }
                    if (idx >= 0) {
                        list[idx] = list[idx].copy(
                            title = dto?.title ?: title,
                            due = dto?.deadline ?: due,
                            course = dto?.source_name ?: course,
                            description = dto?.description ?: description,
                        )
                        _tasks.value = list
                        return@withLock
                    }
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        return@withLock
    }

    suspend fun setMockMode(enabled: Boolean) {
        _mockMode.value = enabled
        expressionSessionManager.setUseMock(enabled)
        dataStore.setMockMode(enabled)
    }

    suspend fun setLearningAssistanceEnabled(enabled: Boolean) {
        _learningAssistanceEnabled.value = enabled
        dataStore.setLearningAssistanceEnabled(enabled)
    }

    suspend fun setReduceMotion(enabled: Boolean) {
        _reduceMotion.value = enabled
        dataStore.setReduceMotion(enabled)
    }

    suspend fun setDarkMode(enabled: Boolean) {
        _darkMode.value = enabled
        dataStore.setDarkMode(enabled)
    }

    suspend fun setRemindersEnabled(enabled: Boolean) {
        _remindersEnabled.value = enabled
        dataStore.setRemindersEnabled(enabled)
    }

    fun getMonitoredGroupChats(): Flow<Set<String>> {
        return dataStore.monitoredGroupChats
    }

    suspend fun addMonitoredGroupChat(groupName: String) {
        dataStore.addMonitoredGroupChat(groupName)
    }

    suspend fun removeMonitoredGroupChat(groupName: String) {
        dataStore.removeMonitoredGroupChat(groupName)
    }

    fun getWecomGroupChats(): Flow<Set<String>> {
        return dataStore.wecomGroupChats
    }

    suspend fun addWecomGroupChat(groupName: String) {
        dataStore.addWecomGroupChat(groupName)
    }

    suspend fun removeWecomGroupChat(groupName: String) {
        dataStore.removeWecomGroupChat(groupName)
    }

    fun getQqGroupChats(): Flow<Set<String>> {
        return dataStore.qqGroupChats
    }

    suspend fun addQqGroupChat(groupName: String) {
        dataStore.addQqGroupChat(groupName)
    }

    suspend fun removeQqGroupChat(groupName: String) {
        dataStore.removeQqGroupChat(groupName)
    }

    suspend fun addFile(name: String, category: String) = personalHubMutex.withLock {
        val cleanName = name.trim()
        if (cleanName.isBlank()) return@withLock
        if (_backendOnline.value && !_mockMode.value) {
            try {
                val resp = ApiClient.api.createFile(
                    PersonalFileCreateRequest(
                        name = cleanName,
                        category = category,
                        source = "手动添加",
                        size_label = "本地记录",
                    )
                )
                if (resp.isSuccessful) {
                    val dto = resp.body() ?: return@withLock
                    val newFile = CampusFile(
                        id = dto.id,
                        name = dto.name,
                        category = dto.category ?: category,
                        sizeLabel = dto.size_label ?: "本地记录",
                        updatedAt = dto.updated_at ?: "刚刚",
                        source = dto.source ?: "手动添加",
                        isFavorite = dto.is_favorite,
                    )
                    _files.value = listOf(newFile) + _files.value
                    persistPersonalHub()
                    return@withLock
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        _files.value = listOf(
            CampusFile(
                id = "local_${System.currentTimeMillis()}",
                name = cleanName,
                category = category,
                sizeLabel = "本地记录",
                updatedAt = "刚刚",
                source = "手动添加",
            ),
        ) + _files.value
        persistPersonalHub()
    }

    suspend fun deleteFile(id: String) = personalHubMutex.withLock {
        if (_backendOnline.value && !_mockMode.value && !id.startsWith("local_")) {
            try {
                val resp = ApiClient.api.deleteFile(id)
                if (resp.isSuccessful) {
                    _files.value = _files.value.filterNot { it.id == id }
                    _favorites.value = _favorites.value.filterNot { it.id == "file:$id" }
                    persistPersonalHub()
                    return@withLock
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        _files.value = _files.value.filterNot { it.id == id }
        _favorites.value = _favorites.value.filterNot { it.id == "file:$id" }
        persistPersonalHub()
    }

    suspend fun toggleFileFavorite(id: String) = personalHubMutex.withLock {
        val target = _files.value.firstOrNull { it.id == id } ?: return@withLock
        val willFavorite = !target.isFavorite
        if (_backendOnline.value && !_mockMode.value && !id.startsWith("local_")) {
            try {
                val resp = ApiClient.api.toggleFileFavorite(
                    id,
                    FileFavoriteToggleRequest(favorite = willFavorite),
                )
                if (resp.isSuccessful) {
                    val dto = resp.body()
                    _files.value = _files.value.map {
                        if (it.id == id) it.copy(isFavorite = dto?.is_favorite ?: willFavorite) else it
                    }
                    _favorites.value = if (willFavorite) {
                        val favId = "file:$id"
                        // 同步到收藏夹
                        if (_backendOnline.value && !_mockMode.value) {
                            try {
                                ApiClient.api.addFavorite(
                                    FavoriteCreateRequest(
                                        id = favId,
                                        title = target.name,
                                        type = "文件",
                                        subtitle = "${target.category} · ${target.source}",
                                        saved_at = "刚刚",
                                        source_route = "files",
                                    )
                                )
                            } catch (_: Exception) { /* 本地仍保留 */ }
                        }
                        listOf(
                            FavoriteItem(
                                id = favId,
                                title = target.name,
                                type = "文件",
                                subtitle = "${target.category} · ${target.source}",
                                savedAt = "刚刚",
                                sourceRoute = "files",
                            ),
                        ) + _favorites.value.filterNot { it.id == favId }
                    } else {
                        val favId = "file:$id"
                        if (_backendOnline.value && !_mockMode.value) {
                            try { ApiClient.api.removeFavorite(favId) } catch (_: Exception) {}
                        }
                        _favorites.value.filterNot { it.id == favId }
                    }
                    persistPersonalHub()
                    return@withLock
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        _files.value = _files.value.map {
            if (it.id == id) it.copy(isFavorite = willFavorite) else it
        }
        _favorites.value = if (willFavorite) {
            listOf(
                FavoriteItem(
                    id = "file:$id",
                    title = target.name,
                    type = "文件",
                    subtitle = "${target.category} · ${target.source}",
                    savedAt = "刚刚",
                    sourceRoute = "files",
                ),
            ) + _favorites.value.filterNot { it.id == "file:$id" }
        } else {
            _favorites.value.filterNot { it.id == "file:$id" }
        }
        persistPersonalHub()
    }

    suspend fun removeFavorite(id: String) = personalHubMutex.withLock {
        if (_backendOnline.value && !_mockMode.value) {
            try { ApiClient.api.removeFavorite(id) } catch (_: Exception) {}
        }
        _favorites.value = _favorites.value.filterNot { it.id == id }
        when {
            id.startsWith("file:") -> {
                val sourceId = id.substringAfter(':')
                _files.value = _files.value.map {
                    if (it.id == sourceId) it.copy(isFavorite = false) else it
                }
            }
        }
        persistPersonalHub()
    }

    fun createExpressionRecognitionService(useMock: Boolean = _mockMode.value): ExpressionRecognitionService =
        if (useMock) {
            MockExpressionRecognitionService()
        } else {
            RealExpressionRecognitionService(application)
        }

    suspend fun updateProfile(
        name: String,
        detail: String,
        email: String,
        phone: String,
        studentId: String,
    ) {
        val current = _session.value ?: throw IllegalStateException("当前未登录")
        val updated = current.copy(
            name = name.trim(),
            detail = detail.trim(),
            email = email.trim(),
            phone = phone.trim(),
            studentId = studentId.trim(),
        )
        _session.value = updated
        dataStore.saveSession(updated)
    }

    /**
     * 搜索大学列表（复用现有 GET /universities 接口）。
     * 用于个人资料编辑页的「所在大学」选择器。
     */
    suspend fun loadUniversities(query: String? = null): List<com.example.campusai.data.remote.UniversityDto> {
        val response = ApiClient.api.listUniversities(query?.takeIf(String::isNotBlank))
        if (!response.isSuccessful) throw Exception("大学列表加载失败 (${response.code()})")
        return response.body()?.items.orEmpty()
    }

    /**
     * 切换当前用户所属大学（复用现有 PUT /profile/university 接口）。
     * 成功后同步更新本地 session 中的 universityId / universityName 并持久化，
     * 保证「我的」页面、首页等订阅 session 的地方立即显示新学校，
     * 且重新进入 App / 重新登录后仍能从后端 me() 读到正确 university_id。
     */
    suspend fun updateUniversity(universityId: String, universityName: String) {
        val response = ApiClient.api.selectUniversity(
            com.example.campusai.data.remote.UniversitySelectionRequest(universityId),
        )
        if (!response.isSuccessful) throw Exception("切换大学失败 (${response.code()})")
        val current = _session.value ?: throw IllegalStateException("当前未登录")
        val updated = current.copy(
            universityId = universityId,
            universityName = universityName,
        )
        _session.value = updated
        dataStore.saveSession(updated)
    }

    /**
     * 若 session 中已有 universityId 但缺 universityName（例如登录时只拿到 id），
     * 通过 listUniversities 拉取并在列表中匹配 id 补全名称，写回 session。
     * 找不到则保持空，不影响主流程。
     */
    suspend fun ensureUniversityNameLoaded() {
        val current = _session.value ?: return
        if (current.universityId.isBlank() || current.universityName.isNotBlank()) return
        val matched = runCatching { loadUniversities(null) }
            .getOrNull()
            ?.firstOrNull { it.id == current.universityId }
            ?: return
        val updated = current.copy(universityName = matched.name)
        _session.value = updated
        dataStore.saveSession(updated)
    }

    suspend fun updateUser(user: User) {
        _session.value = user
        dataStore.saveSession(user)
    }

    suspend fun chat(message: String, expression: ExpressionResult? = null): String {
        if (_backendOnline.value && !_mockMode.value) {
            val expressionSignal = expression
                ?.let { CounselorExpressionPolicy.usableOrNull(it) }
                ?.let {
                    ExpressionSignalRequest(
                        label = it.label.name,
                        confidence = it.confidence.coerceIn(0.0, 1.0),
                        is_stable = true,
                        timestamp = it.timestamp,
                        model_version = it.modelVersion.take(80),
                    )
                }
            val resp = ApiClient.api.chat(
                ChatRequest(
                    message = message,
                    stream = false,
                    expression_signal = expressionSignal,
                ),
            )
            if (resp.isSuccessful) {
                val body = resp.body()!!
                return body.answer ?: body.message ?: "暂无回答"
            }
        }
        return if (message.contains("奖学金")) {
            "奖学金通常综合考察学业成绩、综合素质与志愿服务。不同奖项条件不同，建议先查看学院本学年评审通知。我可以继续帮你整理申请材料清单。"
        } else {
            "我已经记录你的问题。当前为 Mock 知识库模式，建议以学校教务处或学院最新通知为准。需要的话，我可以帮你把相关步骤整理成待办。"
        }
    }

    suspend fun streamChat(
        message: String,
        expression: ExpressionResult? = null,
        onChunk: suspend (String) -> Unit,
    ) {
        if (_mockMode.value) {
            onChunk("**Mock 模式**未连接后端数据库与 DS，无法生成正式的校园事务答复。")
            return
        }
        val expressionSignal = expression
            ?.let { CounselorExpressionPolicy.usableOrNull(it) }
            ?.let {
                ExpressionSignalRequest(
                    label = it.label.name,
                    confidence = it.confidence.coerceIn(0.0, 1.0),
                    is_stable = true,
                    timestamp = it.timestamp,
                    model_version = it.modelVersion.take(80),
                )
            }
        ApiClient.streamCounselor(
            request = ChatRequest(
                message = message,
                stream = true,
                expression_signal = expressionSignal,
            ),
            onChunk = onChunk,
        )
    }

    suspend fun extractNotice(text: String): ExtractResult {
        if (_backendOnline.value && !_mockMode.value) {
            val resp = ApiClient.api.extractNotice(NoticeExtractRequest(content = text))
            if (resp.isSuccessful) return resp.body()?.toExtractResult() ?: ExtractResult(error = "提取失败")
        }
        return ExtractResult(error = "提取服务暂时不可用，请稍后重试。")
    }

    private fun defaultTasks() = listOf(
        Task("demo-1", "《数据结构》作业三：链表与栈", "今天 23:59", "课程作业", false, "实现单链表和双向链表的增删改查操作，并用链表模拟栈的 push/pop。\n\n要求：\n1. 使用 C++ 或 Java 实现\n2. 提交源代码和实验报告\n3. 需要通过 OJ 平台测试"),
        Task("demo-2", "《高等数学》习题课报告提交", "明天 20:00", "课程作业", false, "完成第六章曲线积分与曲面积分的课后练习题，并整理成习题课报告。\n\n报告需包含：\n- 不少于 5 道典型例题的详细解答\n- 知识点总结与易错点归纳"),
        Task("demo-3", "整理创新创业项目资料", "5月21日 18:00", "个人待办", false, "整理已有项目资料并确认下一步计划。\n\n- 汇总项目计划书\n- 整理团队分工\n- 记录需要咨询的问题"),
        Task("demo-4", "图书馆座位预约", "今天 14:00", "学习安排", true, "三楼自习区 A-12 座位，预约时段 14:00-17:00。\n\n记得带校园卡刷卡入座，超时 30 分钟未签到将自动取消。"),
    )

    private fun defaultCourses() = listOf(
        Course(name = "数据结构", code = "CS2103", type = "专业必修", teacher = "张明远", location = "教学楼 2-305"),
        Course(name = "计算机组成原理", code = "CS2201", type = "专业必修", teacher = "刘文青", location = "实验楼 A-204"),
        Course(name = "高等数学（下）", code = "MA1202", type = "学科基础", teacher = "王建国", location = "博学楼 1-401"),
        Course(name = "大学英语 IV", code = "EN1404", type = "公共基础", teacher = "陈思雨", location = "明德楼 3-208"),
        Course(name = "操作系统原理", code = "CS2304", type = "专业核心", teacher = "赵启航", location = "教学楼 4-302"),
        Course(name = "计算机网络", code = "CS2402", type = "专业核心", teacher = "周立新", location = "实验楼 B-310"),
    )

    private fun defaultNotices() = listOf(
        Notice("demo-n-1", "暑期社会实践材料提交提醒", "学生事务", "10:15", true),
        Notice("demo-n-2", "第十六届程序设计竞赛结果公告", "创新实践中心", "昨天", true),
        Notice("demo-n-3", "期末考试安排及相关事项说明", "教务处", "5月17日", false),
        Notice("demo-n-4", "图书馆数据库试用资源更新通知", "图书馆", "5月16日", false),
    )

    private fun defaultCampusNews() = listOf(
        CampusNews(
            id = "news-1",
            title = "图书馆延长开放时间",
            summary = "考试周开放至 22:00，增设自习区域",
            content = """各位同学：

为满足期末考试期间同学们的学习需求，经学校研究决定，图书馆自即日起至本学期结束，开放时间调整如下：

【开放时间】
• 周一至周五：7:00 - 22:00（延长至晚上十点）
• 周六、周日：8:00 - 22:00
• 法定节假日闭馆时间另行通知

【新增自习区域】
• 图书馆一楼大厅新增 50 个临时自习座位，配有独立台灯和电源插座
• 三楼电子阅览室免费开放供自带设备学习
• 研讨室需提前一天通过"校园助手"预约

【温馨提示】
• 请勿占座，离馆时请带走个人物品
• 夜间自习请注意安全，建议结伴同行
• 图书馆入口处设有免费咖啡供应点（每日限量）

图书馆全体工作人员祝同学们考试顺利！""",
            source = "图书馆",
            time = "2026-05-18 09:30",
            category = "学习服务",
            tags = listOf("图书馆", "考试周", "自习", "开放时间"),
        ),
        CampusNews(
            id = "news-2",
            title = "\"互联网+\"校内选拔赛报名",
            summary = "展示你的创意，赢取成长支持与省赛推荐",
            content = """各学院、各位同学：

为选拔优秀项目参加中国国际"互联网+"大学生创新创业大赛省赛，现启动校内选拔赛。

【参赛对象】
我校全日制在校本科生、研究生均可报名，鼓励跨学院、跨专业组队。

【赛道设置】
• 高教主赛道：创意组、初创组、成长组
• "青年红色筑梦之旅"赛道：公益组、商业组

【关键时间节点】
• 报名截止：2026年5月25日 18:00
• 初赛（材料评审）：5月26日 - 5月28日
• 决赛（路演答辩）：6月2日 14:00 大学生活动中心

【报名方式】
请将项目商业计划书（PDF）和路演 PPT 发送至 innovation@campus.edu.cn，邮件标题格式：项目名称-负责人姓名-学院。

【支持政策】
• 获奖项目将获得 1000-5000 元创新创业基金
• 优秀项目直接推荐参加省赛
• 参赛同学可获得第二课堂学分

如有疑问请联系创新实践中心李老师：138 0000 5678""",
            source = "学工处 / 创新实践中心",
            time = "2026-05-17 14:00",
            category = "创新创业",
            tags = listOf("互联网+", "创新创业", "比赛", "报名"),
            relatedTasks = listOf("5月25日前完成报名材料", "准备商业计划书和路演PPT"),
        ),
        CampusNews(
            id = "news-3",
            title = "校园网升级及临时断网通知",
            summary = "教学楼区域周末分时段断网升级",
            content = """各位同学和老师：

为提升校园网络质量，信息中心计划于本周末进行核心网络设备升级。

【升级时间】
• 5月19日（周六）23:00 - 5月20日（周日）06:00
• 预计断网时长不超过 4 小时

【影响范围】
• 教学楼 1-4 栋、实验楼 A/B 栋有线及无线网络
• 图书馆无线网络（有线不受影响）
• 学生宿舍区不受影响

【升级内容】
• 核心交换机固件更新
• 无线 AP 信道优化
• 出口带宽扩容至 10Gbps

【应急安排】
• 紧急事务可前往图书馆一楼使用有线网络终端
• 办公教学如受影响，请联系信息中心 6278-0001

升级完成后，上网体验将有明显改善。感谢大家的理解与配合。""",
            source = "信息中心",
            time = "2026-05-16 16:00",
            category = "校园服务",
            tags = listOf("校园网", "维护", "升级", "通知"),
        ),
        CampusNews(
            id = "news-4",
            title = "期末周图书馆座位还有哪些区域好找？",
            summary = "同学们分享了不同楼层的空位情况和安静程度。",
            content = "想找一个安静、插座方便的位置复习。大家最近在哪个区域比较容易找到座位？也欢迎分享空位和环境情况。",
            source = "校园同学",
            time = "2026-05-15 10:00",
            category = "学习交流",
            tags = listOf("热度 128", "图书馆", "期末周"),
        ),
    )

    private fun bindPersonalHub(user: User?) {
        personalHubJob?.cancel()
        if (user == null) {
            activeAccountKey = null
            _personalHubLoading.value = false
            _files.value = emptyList()
            _favorites.value = emptyList()
            return
        }
        val accountKey = accountStorageKey(user)
        activeAccountKey = accountKey
        _personalHubLoading.value = true
        personalHubJob = scope.launch {
            dataStore.observePersonalHub(accountKey).collect { stored ->
                val snapshot = stored ?: defaultPersonalHub().also {
                    dataStore.savePersonalHub(accountKey, it)
                }
                if (stored != null && personalHubMigratedAccountKeys.add(accountKey)) {
                    dataStore.savePersonalHub(accountKey, snapshot)
                }
                _files.value = snapshot.files
                _favorites.value = snapshot.favorites
                _personalHubLoading.value = false
            }
        }
    }

    suspend fun uploadExpressionContribution(
        imageFile: File,
        label: ExpressionLabel,
    ): String {
        check(!_mockMode.value) { "Mock 模式不上传模型共建样本" }
        check(_backendOnline.value) { "后端未连接，暂时无法上传样本" }
        val imageBody = imageFile.asRequestBody("image/jpeg".toMediaType())
        val imagePart = MultipartBody.Part.createFormData(
            "image",
            imageFile.name,
            imageBody,
        )
        val response = ApiClient.api.uploadExpressionContribution(
            image = imagePart,
            label = label.name.toRequestBody("text/plain".toMediaType()),
            consent = "true".toRequestBody("text/plain".toMediaType()),
            modelVersion = "client-expression-v1".toRequestBody("text/plain".toMediaType()),
        )
        if (!response.isSuccessful) {
            throw IllegalStateException("样本上传失败(${response.code()})")
        }
        return response.body()?.sample_id ?: throw IllegalStateException("样本上传响应为空")
    }

    suspend fun deleteExpressionContribution(sampleId: String) {
        check(!_mockMode.value) { "Mock 模式没有云端样本" }
        check(_backendOnline.value) { "后端未连接，暂时无法删除样本" }
        val response = ApiClient.api.deleteExpressionContribution(sampleId)
        if (!response.isSuccessful) {
            throw IllegalStateException("样本删除失败(${response.code()})")
        }
    }

    private fun bindTasks(user: User?) {
        taskJob?.cancel()
        _tasks.value = emptyList()
        if (user == null) {
            return
        }
        taskJob = scope.launch {
            refreshTasks()
        }
    }

    private suspend fun persistTasks() {
        val user = _session.value ?: return
        dataStore.saveRaw("tasks_${accountStorageKey(user)}", encodeTasks(_tasks.value))
    }

    private fun encodeTasks(tasks: List<Task>): String = JSONArray().apply {
        tasks.forEach { task ->
            put(JSONObject().apply {
                put("id", task.id)
                put("title", task.title)
                put("due", task.due)
                put("course", task.course)
                put("done", task.done)
                put("description", task.description)
            })
        }
    }.toString()

    private fun decodeTasks(raw: String): List<Task>? = try {
        val json = JSONArray(raw)
        List(json.length()) { index ->
            json.getJSONObject(index).let { item ->
                Task(
                    // 兼容历史 Long id 与新 String id
                    id = item.optString("id").ifBlank { item.optLong("id").toString() },
                    title = item.optString("title"),
                    due = item.optString("due"),
                    course = item.optString("course"),
                    done = item.optBoolean("done"),
                    description = item.optString("description"),
                )
            }
        }
    } catch (_: Exception) {
        null
    }

    private suspend fun persistPersonalHub() {
        val accountKey = activeAccountKey ?: return
        dataStore.savePersonalHub(
            accountKey,
            PersonalHubSnapshot(
                files = _files.value,
                favorites = _favorites.value,
            ),
        )
    }

    private fun accountStorageKey(user: User): String {
        val identity = user.accountId.ifBlank {
            user.studentId.ifBlank { user.email.ifBlank { "${user.role}:${user.name}" } }
        }
        return MessageDigest.getInstance("SHA-256")
            .digest(identity.toByteArray())
            .take(12)
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }

    private fun defaultPersonalHub(): PersonalHubSnapshot {
        val files = listOf(
            CampusFile(id = "demo-f-1", name = "数据结构实验三说明.pdf", category = "课程资料", sizeLabel = "2.4 MB", updatedAt = "今天 10:24", source = "数据结构", isFavorite = true),
            CampusFile(id = "demo-f-2", name = "奖学金申请材料清单.docx", category = "校园事务", sizeLabel = "860 KB", updatedAt = "昨天 18:40", source = "学生工作处"),
            CampusFile(id = "demo-f-3", name = "创新创业训练计划书.pdf", category = "竞赛资料", sizeLabel = "1.7 MB", updatedAt = "7月28日", source = "创新实践中心"),
        )
        return PersonalHubSnapshot(
            files = files,
            favorites = listOf(
                FavoriteItem("file:demo-f-1", files.first().name, "文件", "课程资料 · 数据结构", "7月29日", "files"),
                FavoriteItem("notice:scholarship", "2026 学年奖学金评审通知", "通知", "学生工作处 · 申请流程", "7月26日", "notifications"),
            ),
        )
    }
}
