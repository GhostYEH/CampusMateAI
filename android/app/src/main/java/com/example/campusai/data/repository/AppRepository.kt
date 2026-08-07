package com.example.campusai.data.repository

import android.app.Application
import com.example.campusai.data.local.AppDataStore
import com.example.campusai.data.expression.ExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionSessionManager
import com.example.campusai.data.expression.MockExpressionRecognitionService
import com.example.campusai.data.expression.RealExpressionRecognitionService
import com.example.campusai.data.model.*
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.LoginRequest
import com.example.campusai.data.remote.ChatRequest
import com.example.campusai.data.remote.ExpressionSignalRequest
import com.example.campusai.data.remote.ExtractRequest
import com.example.campusai.data.remote.PersonalTaskCreateRequest
import com.example.campusai.data.remote.PersonalTaskUpdateRequest
import com.example.campusai.data.remote.PersonalFileCreateRequest
import com.example.campusai.data.remote.FileFavoriteToggleRequest
import com.example.campusai.data.remote.FavoriteCreateRequest
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

class AppRepository(application: Application) {

    data class BackendStatus(
        val online: Boolean,
        val mode: String,
        val knowledgeDocuments: Int?,
        val indexReady: Boolean?,
        val error: String? = null,
    )

    private val application = application
    private val dataStore = AppDataStore(application)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _session = MutableStateFlow<User?>(null)
    val session: StateFlow<User?> = _session.asStateFlow()

    private val _backendOnline = MutableStateFlow(false)
    val backendOnline: StateFlow<Boolean> = _backendOnline.asStateFlow()

    private val _mockMode = MutableStateFlow(BuildConfig.DEFAULT_USE_MOCK)
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
    private val _tasks = MutableStateFlow<List<Task>>(defaultTasks())
    val tasks: StateFlow<List<Task>> = _tasks.asStateFlow()

    val pendingCount: StateFlow<Int> = _tasks
        .map { list -> list.count { !it.done } }
        .stateIn(scope, SharingStarted.Eagerly, 0)

    private val _notices = MutableStateFlow(defaultNotices())
    val notices: StateFlow<List<Notice>> = _notices.asStateFlow()

    private val _campusNews = MutableStateFlow(defaultCampusNews())
    val campusNews: StateFlow<List<CampusNews>> = _campusNews.asStateFlow()

    fun getCampusNewsById(id: String): CampusNews? = _campusNews.value.find { it.id == id }

    private val _courses = MutableStateFlow(defaultCourses())
    val courses: StateFlow<List<Course>> = _courses.asStateFlow()

    private val personalHubMutex = Mutex()
    private var personalHubJob: Job? = null
    private var activeAccountKey: String? = null

    private val _files = MutableStateFlow<List<CampusFile>>(emptyList())
    val files: StateFlow<List<CampusFile>> = _files.asStateFlow()

    private val _activities = MutableStateFlow<List<CampusActivity>>(emptyList())
    val activities: StateFlow<List<CampusActivity>> = _activities.asStateFlow()

    private val _favorites = MutableStateFlow<List<FavoriteItem>>(emptyList())
    val favorites: StateFlow<List<FavoriteItem>> = _favorites.asStateFlow()

    private val _personalHubLoading = MutableStateFlow(false)
    val personalHubLoading: StateFlow<Boolean> = _personalHubLoading.asStateFlow()

    private val demos = mapOf(
        "student_demo" to User("林知夏", "student", "计算机科学与技术 · 大三", "lin.zhixia@campus.edu.cn", "138 0000 2026", "2024020318"),
    )

    init {
        scope.launch {
            dataStore.session.collect { stored ->
                val defaults = stored?.let { user ->
                    demos.values.firstOrNull { it.name == user.name && it.role == user.role }
                }
                val hydrated = if (stored != null && defaults != null) {
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
        scope.launch { dataStore.mockMode.collect {
            _mockMode.value = it
            expressionSessionManager.setUseMock(it)
        } }
        scope.launch { dataStore.reduceMotion.collect { _reduceMotion.value = it } }
        scope.launch { dataStore.darkMode.collect { _darkMode.value = it } }
        scope.launch { dataStore.remindersEnabled.collect { _remindersEnabled.value = it } }
        scope.launch { dataStore.learningAssistanceEnabled.collect { _learningAssistanceEnabled.value = it } }
    }

    suspend fun login(username: String, password: String): User {
        _backendOnline.value = if (_mockMode.value) false else ApiClient.probeBackend()
        val user: User
        if (_backendOnline.value && !_mockMode.value) {
            val loginResp = ApiClient.api.login(LoginRequest(username, password))
            if (!loginResp.isSuccessful) throw Exception("账号或密码不正确")
            val body = loginResp.body()!!
            ApiClient.setToken(body.access_token)
            dataStore.saveTokens(body.access_token, body.refresh_token)
            val meResp = ApiClient.api.me()
            val meUser = meResp.body()?.user
            user = User(
                name = meUser?.name ?: username,
                role = meUser?.role ?: "student",
                detail = meUser?.detail ?: "",
                accountId = meUser?.account_id.orEmpty(),
            )
        } else {
            val demo = demos[username]
            if (demo == null || password != "Demo123456") throw Exception("账号或密码不正确")
            user = demo
        }
        _session.value = user
        dataStore.saveSession(user)
        return user
    }

    suspend fun loginChaoxing(username: String, password: String): Pair<Boolean, String> {
        return try {
            val req = com.example.campusai.data.remote.ChaoxingLoginRequest(username, password)
            val resp = ApiClient.api.loginChaoxing(req)
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
            val resp = ApiClient.api.syncChaoxing()
            if (resp.isSuccessful) {
                Pair(true, "")
            } else {
                val errorStr = resp.errorBody()?.string() ?: ""
                if (resp.code() == 401 || errorStr.contains("reauth_required")) {
                    Pair(false, "reauth_required")
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
            val resp = ApiClient.api.getChaoxingStatus()
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
    }

    suspend fun refreshBackendStatus(): BackendStatus {
        if (_mockMode.value) {
            _backendOnline.value = false
            return BackendStatus(false, "Mock 演示模式", null, null)
        }
        return try {
            val health = ApiClient.api.health()
            val knowledge = ApiClient.api.knowledgeStatus()
            val online = health.isSuccessful
            _backendOnline.value = online
            BackendStatus(
                online = online,
                mode = health.body()?.mode ?: "Real",
                knowledgeDocuments = knowledge.body()?.document_count,
                indexReady = knowledge.body()?.index_ready,
                error = if (online) null else "健康检查返回 ${health.code()}",
            )
        } catch (error: Exception) {
            _backendOnline.value = false
            BackendStatus(false, "Real", null, null, error.message ?: "无法连接后端")
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

    /** 拉取校园动态（来自全校活动）。 */
    suspend fun refreshCampusNews() {
        if (!_backendOnline.value || _mockMode.value) return
        try {
            val resp = ApiClient.api.listActivities(page = 1, pageSize = 50)
            if (resp.isSuccessful) {
                val items = resp.body()?.items.orEmpty()
                if (items.isNotEmpty()) {
                    _campusNews.value = items.map { dto ->
                        CampusNews(
                            id = dto.id,
                            title = dto.title,
                            summary = dto.summary ?: "",
                            content = dto.content ?: "",
                            source = dto.author_name ?: "校园活动",
                            time = dto.published_at ?: dto.created_at ?: "",
                            category = dto.category ?: "校园活动",
                            tags = emptyList(),
                            relatedTasks = emptyList(),
                        )
                    }
                }
            }
        } catch (_: Exception) { /* 保留现有数据 */ }
    }

    /** 拉取课程列表。 */
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
                        )
                    }
                }
            }
        } catch (_: Exception) { /* 保留现有数据 */ }
    }

    /** 拉取云端任务并合并到本地缓存。 */
    suspend fun refreshTasks() {
        if (!_backendOnline.value || _mockMode.value) return
        try {
            val resp = ApiClient.api.listTasks(page = 1, pageSize = 200)
            if (resp.isSuccessful) {
                val items = resp.body()?.items.orEmpty()
                if (items.isNotEmpty()) {
                    _tasks.value = items.map { dto ->
                        Task(
                            id = dto.id,
                            title = dto.title,
                            due = dto.deadline ?: "待设置",
                            course = dto.source_name ?: "个人待办",
                            done = dto.status == "completed",
                            description = dto.description ?: dto.source_text ?: "",
                        )
                    }
                    persistTasks()
                }
            }
        } catch (_: Exception) { /* 保留现有数据 */ }
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
            // 「我的活动」复用 /activities
            val actResp = ApiClient.api.listActivities(page = 1, pageSize = 50)
            if (actResp.isSuccessful) {
                val items = actResp.body()?.items.orEmpty()
                val favIds = _favorites.value.map { it.id }.toSet()
                _activities.value = items.map { dto ->
                    val isFav = "activity:${dto.id}" in favIds
                    CampusActivity(
                        id = dto.id,
                        title = dto.title,
                        organizer = dto.author_name ?: "校园活动",
                        date = dto.starts_at ?: dto.published_at ?: "",
                        location = dto.location ?: "",
                        status = if (dto.status == "closed") "已结束" else "可报名",
                        isFavorite = isFav,
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
                        persistTasks()
                        return@withLock
                    }
                } catch (_: Exception) { /* 落入本地回退 */ }
            }
            list[idx] = current.copy(done = newDone)
            _tasks.value = list
            persistTasks()
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
                    persistTasks()
                    return@withLock
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        val list = _tasks.value.toMutableList()
        list.add(0, Task(id = "local_${System.currentTimeMillis()}", title = title, due = due, course = course, done = false, description = description))
        _tasks.value = list
        persistTasks()
    }

    suspend fun deleteTask(id: String) = taskMutex.withLock {
        if (_backendOnline.value && !_mockMode.value && !id.startsWith("local_")) {
            try {
                val resp = ApiClient.api.deleteTask(id)
                if (resp.isSuccessful) {
                    _tasks.value = _tasks.value.filter { it.id != id }
                    persistTasks()
                    return@withLock
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        _tasks.value = _tasks.value.filter { it.id != id }
        persistTasks()
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
                        persistTasks()
                        return@withLock
                    }
                }
            } catch (_: Exception) { /* 落入本地回退 */ }
        }
        val list = _tasks.value.toMutableList()
        val idx = list.indexOfFirst { it.id == id }
        if (idx >= 0) {
            list[idx] = list[idx].copy(title = title, due = due, course = course, description = description)
            _tasks.value = list
            persistTasks()
        }
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

    suspend fun toggleActivityJoined(id: String) = personalHubMutex.withLock {
        _activities.value = _activities.value.map { activity ->
            if (activity.id != id) activity
            else activity.copy(status = if (activity.status == "已报名") "可报名" else "已报名")
        }
        persistPersonalHub()
    }

    suspend fun toggleActivityFavorite(id: String) = personalHubMutex.withLock {
        val target = _activities.value.firstOrNull { it.id == id } ?: return@withLock
        val willFavorite = !target.isFavorite
        _activities.value = _activities.value.map {
            if (it.id == id) it.copy(isFavorite = willFavorite) else it
        }
        val favId = "activity:$id"
        _favorites.value = if (willFavorite) {
            if (_backendOnline.value && !_mockMode.value) {
                try {
                    ApiClient.api.addFavorite(
                        FavoriteCreateRequest(
                            id = favId,
                            title = target.title,
                            type = "活动",
                            subtitle = "${target.date} · ${target.organizer}",
                            saved_at = "刚刚",
                            source_route = "activities",
                        )
                    )
                } catch (_: Exception) { /* 本地仍保留 */ }
            }
            listOf(
                FavoriteItem(
                    id = favId,
                    title = target.title,
                    type = "活动",
                    subtitle = "${target.date} · ${target.organizer}",
                    savedAt = "刚刚",
                    sourceRoute = "activities",
                ),
            ) + _favorites.value.filterNot { it.id == favId }
        } else {
            if (_backendOnline.value && !_mockMode.value) {
                try { ApiClient.api.removeFavorite(favId) } catch (_: Exception) {}
            }
            _favorites.value.filterNot { it.id == favId }
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
            id.startsWith("activity:") -> {
                val sourceId = id.substringAfter(':')
                _activities.value = _activities.value.map {
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

    suspend fun updateUser(user: User) {
        _session.value = user
        dataStore.saveSession(user)
    }

    suspend fun chat(message: String, expression: ExpressionResult? = null): String {
        if (_backendOnline.value && !_mockMode.value) {
            val expressionSignal = expression
                ?.takeIf {
                    it.isStable &&
                        it.confidence >= 0.60 &&
                        it.label != ExpressionLabel.UNKNOWN &&
                        it.label != ExpressionLabel.NO_FACE
                }
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

    suspend fun extractNotice(text: String): ExtractResult {
        if (_backendOnline.value && !_mockMode.value) {
            val resp = ApiClient.api.extractNotice(ExtractRequest(text))
            if (resp.isSuccessful) return resp.body() ?: ExtractResult(error = "提取失败")
        }
        return ExtractResult(
            title = "2026年秋季学期选课确认",
            source = "教务处",
            deadline = "本周五 17:00",
            tasks = listOf("登录教务系统核对课程信息", "如有冲突联系学院教务办公室"),
            confidence = 0.94
        )
    }

    suspend fun enqueueNoticeIngestion(content: String, sourceName: String, publishedAt: String) {
        val id = java.util.UUID.randomUUID().toString()
        val notice = PendingNotice(
            id = id,
            content = content,
            sourceName = sourceName,
            publishedAt = publishedAt,
            retryCount = 0,
            status = "pending"
        )
        dataStore.enqueuePendingNotice(notice)

        // Trigger WorkManager
        val constraints = androidx.work.Constraints.Builder()
            .setRequiredNetworkType(androidx.work.NetworkType.CONNECTED)
            .build()
            
        val workRequest = androidx.work.OneTimeWorkRequestBuilder<com.example.campusai.workers.NoticeUploadWorker>()
            .setConstraints(constraints)
            .build()
            
        androidx.work.WorkManager.getInstance(application).enqueueUniqueWork(
            "NoticeUploadWorker",
            androidx.work.ExistingWorkPolicy.REPLACE,
            workRequest
        )
    }

    suspend fun scheduleNoticeUploadWorker() {
        val constraints = androidx.work.Constraints.Builder()
            .setRequiredNetworkType(androidx.work.NetworkType.CONNECTED)
            .build()
            
        val workRequest = androidx.work.OneTimeWorkRequestBuilder<com.example.campusai.workers.NoticeUploadWorker>()
            .setConstraints(constraints)
            .build()
            
        androidx.work.WorkManager.getInstance(application).enqueueUniqueWork(
            "NoticeUploadWorker",
            androidx.work.ExistingWorkPolicy.REPLACE,
            workRequest
        )
    }

    suspend fun getPendingNotices(): List<PendingNotice> = dataStore.pendingNotices.first()

    suspend fun updatePendingNotices(notices: List<PendingNotice>) {
        dataStore.savePendingNotices(notices)
    }

    suspend fun ingestNoticeDirectly(notice: PendingNotice): Boolean {
        if (!_backendOnline.value || _mockMode.value) return false
        return try {
            val response = ApiClient.api.ingestNotice(
                com.example.campusai.data.remote.NoticeIngestRequest(
                    content = notice.content,
                    source_name = notice.sourceName,
                    published_at = notice.publishedAt
                )
            )
            response.isSuccessful
        } catch (e: Exception) {
            false
        }
    }

    suspend fun ingestNotice(content: String, sourceName: String, publishedAt: String) {
        // Obsolete, use enqueueNoticeIngestion instead
    }



    private fun defaultTasks() = listOf(
        Task("demo-1", "《数据结构》作业三：链表与栈", "今天 23:59", "课程作业", false, "实现单链表和双向链表的增删改查操作，并用链表模拟栈的 push/pop。\n\n要求：\n1. 使用 C++ 或 Java 实现\n2. 提交源代码和实验报告\n3. 需要通过 OJ 平台测试"),
        Task("demo-2", "《高等数学》习题课报告提交", "明天 20:00", "课程作业", false, "完成第六章曲线积分与曲面积分的课后练习题，并整理成习题课报告。\n\n报告需包含：\n- 不少于 5 道典型例题的详细解答\n- 知识点总结与易错点归纳"),
        Task("demo-3", "\"互联网+\"大赛校内选拔报名", "5月21日 18:00", "活动报名", false, "第八届中国国际\"互联网+\"大学生创新创业大赛校内选拔赛。\n\n报名材料：\n- 项目计划书（PDF）\n- 团队信息表\n- 指导教师推荐意见\n\n报名网站：校创新创业中心官网"),
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
        Notice("demo-n-1", "关于开展暑期社会实践活动的通知", "学生事务", "10:15", true),
        Notice("demo-n-2", "第十六届程序设计竞赛报名通知", "创新实践中心", "昨天", true),
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
            title = "心理健康月系列活动预告",
            summary = "关注心灵成长，拥抱阳光生活",
            content = """亲爱的同学们：

五月是心理健康月，校心理健康教育中心策划了丰富多彩的活动，诚邀大家参与。

【活动安排】

🌿 "心灵驿站"开放日
• 时间：5月20日-24日 每日 14:00-17:00
• 地点：学生活动中心二楼心理健康中心
• 内容：心理沙盘体验、放松训练、一对一咨询体验

📝 "写给未来自己的一封信"
• 在心理健康中心领取信纸，写好后投入"时光信箱"
• 一年后由中心寄还给你
• 活动持续整个五月

🎬 心理电影展播
• 5月21日 19:00《心灵奇旅》- 图书馆报告厅
• 映后有心理咨询师带领的分享交流环节

👥 团体辅导工作坊
• "情绪管理与压力应对" 5月23日 15:00
• "人际关系沟通技巧" 5月25日 15:00
• 每场限 20 人，请提前扫码报名

所有活动免费向全校学生开放。如有任何心理困扰，欢迎随时预约咨询（预约电话：6278-6688）。""",
            source = "心理健康教育中心",
            time = "2026-05-15 10:00",
            category = "校园活动",
            tags = listOf("心理健康", "活动", "团体辅导", "电影展播"),
        ),
    )

    private fun bindPersonalHub(user: User?) {
        personalHubJob?.cancel()
        if (user == null) {
            activeAccountKey = null
            _personalHubLoading.value = false
            _files.value = emptyList()
            _activities.value = emptyList()
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
                _files.value = snapshot.files
                _activities.value = snapshot.activities
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
        if (user == null) {
            _tasks.value = defaultTasks()
            return
        }
        val key = "tasks_${accountStorageKey(user)}"
        taskJob = scope.launch {
            dataStore.observeRaw(key).collect { raw ->
                val stored = raw?.let(::decodeTasks)
                if (stored == null) {
                    val defaults = defaultTasks()
                    _tasks.value = defaults
                    dataStore.saveRaw(key, encodeTasks(defaults))
                } else {
                    _tasks.value = stored
                }
            }
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
                activities = _activities.value,
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
        val activities = listOf(
            CampusActivity(id = "demo-a-1", title = "第十六届程序设计竞赛", organizer = "创新实践中心", date = "8月16日 09:00", location = "信息楼报告厅", status = "已报名", isFavorite = true),
            CampusActivity(id = "demo-a-2", title = "图书馆新生志愿讲解员招募", organizer = "校图书馆", date = "8月20日 14:30", location = "图书馆一层", status = "可报名"),
            CampusActivity(id = "demo-a-3", title = "暑期社会实践成果分享会", organizer = "校团委", date = "9月03日 19:00", location = "大学生活动中心", status = "可报名"),
        )
        return PersonalHubSnapshot(
            files = files,
            activities = activities,
            favorites = listOf(
                FavoriteItem("activity:demo-a-1", activities.first().title, "活动", "8月16日 · 创新实践中心", "7月30日", "activities"),
                FavoriteItem("file:demo-f-1", files.first().name, "文件", "课程资料 · 数据结构", "7月29日", "files"),
                FavoriteItem("notice:scholarship", "2026 学年奖学金评审通知", "通知", "学生工作处 · 申请流程", "7月26日", "notifications"),
            ),
        )
    }
}
