package com.example.campusai.data.repository

import android.app.Application
import com.example.campusai.data.local.AppDataStore
import com.example.campusai.data.model.*
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.LoginRequest
import com.example.campusai.data.remote.ChatRequest
import com.example.campusai.data.remote.ExtractRequest
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class AppRepository(application: Application) {

    private val dataStore = AppDataStore(application)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _session = MutableStateFlow<User?>(null)
    val session: StateFlow<User?> = _session.asStateFlow()

    private val _backendOnline = MutableStateFlow(false)
    val backendOnline: StateFlow<Boolean> = _backendOnline.asStateFlow()

    private val _mockMode = MutableStateFlow(true)
    val mockMode: StateFlow<Boolean> = _mockMode.asStateFlow()

    private val _reduceMotion = MutableStateFlow(false)
    val reduceMotion: StateFlow<Boolean> = _reduceMotion.asStateFlow()

    private val _darkMode = MutableStateFlow(false)
    val darkMode: StateFlow<Boolean> = _darkMode.asStateFlow()

    private val _remindersEnabled = MutableStateFlow(true)
    val remindersEnabled: StateFlow<Boolean> = _remindersEnabled.asStateFlow()

    private val _demoMode = MutableStateFlow(true)
    val demoMode: StateFlow<Boolean> = _demoMode.asStateFlow()

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
            }
        }
        scope.launch { dataStore.mockMode.collect { _mockMode.value = it } }
        scope.launch { dataStore.reduceMotion.collect { _reduceMotion.value = it } }
        scope.launch { dataStore.darkMode.collect { _darkMode.value = it } }
        scope.launch { dataStore.remindersEnabled.collect { _remindersEnabled.value = it } }
        scope.launch { dataStore.demoMode.collect { _demoMode.value = it } }
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
                detail = meUser?.detail ?: ""
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

    suspend fun setDemoMode(enabled: Boolean) {
        _demoMode.value = enabled
        dataStore.setDemoMode(enabled)
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

    suspend fun chat(message: String): String {
        if (_backendOnline.value && !_mockMode.value) {
            val resp = ApiClient.api.chat(ChatRequest(message))
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
}
