package com.example.campusai.data.repository

import android.app.Application
import com.example.campusai.data.local.AppDataStore
import com.example.campusai.data.expression.ExpressionRecognitionService
import com.example.campusai.data.expression.MockExpressionRecognitionService
import com.example.campusai.data.expression.RealExpressionRecognitionService
import com.example.campusai.data.model.*
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.LoginRequest
import com.example.campusai.data.remote.ChatRequest
import com.example.campusai.data.remote.ExpressionSignalRequest
import com.example.campusai.data.remote.ExtractRequest
import com.example.campusai.BuildConfig
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.security.MessageDigest

class AppRepository(application: Application) {

    private val application = application
    private val dataStore = AppDataStore(application)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _session = MutableStateFlow<User?>(null)
    val session: StateFlow<User?> = _session.asStateFlow()

    private val _backendOnline = MutableStateFlow(false)
    val backendOnline: StateFlow<Boolean> = _backendOnline.asStateFlow()

    private val _mockMode = MutableStateFlow(BuildConfig.DEBUG)
    val mockMode: StateFlow<Boolean> = _mockMode.asStateFlow()

    private val _reduceMotion = MutableStateFlow(false)
    val reduceMotion: StateFlow<Boolean> = _reduceMotion.asStateFlow()

    private val _darkMode = MutableStateFlow(false)
    val darkMode: StateFlow<Boolean> = _darkMode.asStateFlow()

    private val _remindersEnabled = MutableStateFlow(true)
    val remindersEnabled: StateFlow<Boolean> = _remindersEnabled.asStateFlow()


    private val taskMutex = Mutex()
    private val _tasks = MutableStateFlow<List<Task>>(defaultTasks())
    val tasks: StateFlow<List<Task>> = _tasks.asStateFlow()

    val pendingCount: StateFlow<Int> = _tasks
        .map { list -> list.count { !it.done } }
        .stateIn(scope, SharingStarted.Eagerly, 0)

    private val _notices = MutableStateFlow(defaultNotices())
    val notices: StateFlow<List<Notice>> = _notices.asStateFlow()

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
        "teacher_demo" to User("张明远", "teacher", "计算机学院 · 副教授", "zhang.mingyuan@campus.edu.cn", "", "T20180306"),
        "admin_demo" to User("系统管理员", "admin", "信息中心", "admin@campus.edu.cn", "", "A0001"),
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
            }
        }
        scope.launch { dataStore.mockMode.collect { _mockMode.value = it } }
        scope.launch { dataStore.reduceMotion.collect { _reduceMotion.value = it } }
        scope.launch { dataStore.darkMode.collect { _darkMode.value = it } }
        scope.launch { dataStore.remindersEnabled.collect { _remindersEnabled.value = it } }
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

    suspend fun logout() {
        _session.value = null
        ApiClient.setToken(null)
        dataStore.clearSession()
    }

    suspend fun toggleTask(id: Long) = taskMutex.withLock {
        val list = _tasks.value.toMutableList()
        val idx = list.indexOfFirst { it.id == id }
        if (idx >= 0) {
            list[idx] = list[idx].copy(done = !list[idx].done)
            _tasks.value = list
        }
    }

    suspend fun addTask(title: String, due: String = "待设置") = taskMutex.withLock {
        val list = _tasks.value.toMutableList()
        list.add(0, Task(id = System.currentTimeMillis(), title = title, due = due, course = "个人待办", done = false))
        _tasks.value = list
    }

    suspend fun deleteTask(id: Long) = taskMutex.withLock {
        _tasks.value = _tasks.value.filter { it.id != id }
    }

    suspend fun setMockMode(enabled: Boolean) {
        _mockMode.value = enabled
        dataStore.setMockMode(enabled)
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

    suspend fun addFile(name: String, category: String) = personalHubMutex.withLock {
        val cleanName = name.trim()
        if (cleanName.isBlank()) return@withLock
        _files.value = listOf(
            CampusFile(
                id = System.currentTimeMillis(),
                name = cleanName,
                category = category,
                sizeLabel = "本地记录",
                updatedAt = "刚刚",
                source = "手动添加",
            ),
        ) + _files.value
        persistPersonalHub()
    }

    suspend fun deleteFile(id: Long) = personalHubMutex.withLock {
        _files.value = _files.value.filterNot { it.id == id }
        _favorites.value = _favorites.value.filterNot { it.id == "file:$id" }
        persistPersonalHub()
    }

    suspend fun toggleFileFavorite(id: Long) = personalHubMutex.withLock {
        val target = _files.value.firstOrNull { it.id == id } ?: return@withLock
        val willFavorite = !target.isFavorite
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

    suspend fun toggleActivityJoined(id: Long) = personalHubMutex.withLock {
        _activities.value = _activities.value.map { activity ->
            if (activity.id != id) activity
            else activity.copy(status = if (activity.status == "已报名") "可报名" else "已报名")
        }
        persistPersonalHub()
    }

    suspend fun toggleActivityFavorite(id: Long) = personalHubMutex.withLock {
        val target = _activities.value.firstOrNull { it.id == id } ?: return@withLock
        val willFavorite = !target.isFavorite
        _activities.value = _activities.value.map {
            if (it.id == id) it.copy(isFavorite = willFavorite) else it
        }
        _favorites.value = if (willFavorite) {
            listOf(
                FavoriteItem(
                    id = "activity:$id",
                    title = target.title,
                    type = "活动",
                    subtitle = "${target.date} · ${target.organizer}",
                    savedAt = "刚刚",
                    sourceRoute = "activities",
                ),
            ) + _favorites.value.filterNot { it.id == "activity:$id" }
        } else {
            _favorites.value.filterNot { it.id == "activity:$id" }
        }
        persistPersonalHub()
    }

    suspend fun removeFavorite(id: String) = personalHubMutex.withLock {
        _favorites.value = _favorites.value.filterNot { it.id == id }
        when {
            id.startsWith("file:") -> {
                val sourceId = id.substringAfter(':').toLongOrNull()
                _files.value = _files.value.map {
                    if (it.id == sourceId) it.copy(isFavorite = false) else it
                }
            }
            id.startsWith("activity:") -> {
                val sourceId = id.substringAfter(':').toLongOrNull()
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

    private fun defaultTasks() = listOf(
        Task(1, "《数据结构》作业三：链表与栈", "今天 23:59", "课程作业", false),
        Task(2, "《高等数学》习题课报告提交", "明天 20:00", "课程作业", false),
        Task(3, "\"互联网+\"大赛校内选拔报名", "5月21日 18:00", "活动报名", false),
        Task(4, "图书馆座位预约", "今天 14:00", "学习安排", true),
    )

    private fun defaultCourses() = listOf(
        Course("数据结构", "CS2103", "专业必修", "张明远", "教学楼 2-305"),
        Course("计算机组成原理", "CS2201", "专业必修", "刘文青", "实验楼 A-204"),
        Course("高等数学（下）", "MA1202", "学科基础", "王建国", "博学楼 1-401"),
        Course("大学英语 IV", "EN1404", "公共基础", "陈思雨", "明德楼 3-208"),
        Course("操作系统原理", "CS2304", "专业核心", "赵启航", "教学楼 4-302"),
        Course("计算机网络", "CS2402", "专业核心", "周立新", "实验楼 B-310"),
    )

    private fun defaultNotices() = listOf(
        Notice(1, "关于开展暑期社会实践活动的通知", "学生事务", "10:15", true),
        Notice(2, "第十六届程序设计竞赛报名通知", "创新实践中心", "昨天", true),
        Notice(3, "期末考试安排及相关事项说明", "教务处", "5月17日", false),
        Notice(4, "图书馆数据库试用资源更新通知", "图书馆", "5月16日", false),
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
            CampusFile(101, "数据结构实验三说明.pdf", "课程资料", "2.4 MB", "今天 10:24", "数据结构", true),
            CampusFile(102, "奖学金申请材料清单.docx", "校园事务", "860 KB", "昨天 18:40", "学生工作处"),
            CampusFile(103, "创新创业训练计划书.pdf", "竞赛资料", "1.7 MB", "7月28日", "创新实践中心"),
        )
        val activities = listOf(
            CampusActivity(201, "第十六届程序设计竞赛", "创新实践中心", "8月16日 09:00", "信息楼报告厅", "已报名", true),
            CampusActivity(202, "图书馆新生志愿讲解员招募", "校图书馆", "8月20日 14:30", "图书馆一层", "可报名"),
            CampusActivity(203, "暑期社会实践成果分享会", "校团委", "9月03日 19:00", "大学生活动中心", "可报名"),
        )
        return PersonalHubSnapshot(
            files = files,
            activities = activities,
            favorites = listOf(
                FavoriteItem("activity:201", activities.first().title, "活动", "8月16日 · 创新实践中心", "7月30日", "activities"),
                FavoriteItem("file:101", files.first().name, "文件", "课程资料 · 数据结构", "7月29日", "files"),
                FavoriteItem("notice:scholarship", "2026 学年奖学金评审通知", "通知", "学生工作处 · 申请流程", "7月26日", "notifications"),
            ),
        )
    }
}
