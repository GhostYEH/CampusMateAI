package com.example.campusai.data.repository

import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.EduBindingDto
import com.example.campusai.data.remote.EduConnectionContinueRequest
import com.example.campusai.data.remote.EduConnectionDto
import com.example.campusai.data.remote.EduConnectionFromUrlRequest
import com.example.campusai.data.remote.EduGradeItemsResponse
import com.example.campusai.data.remote.EduPreLoginResult
import com.example.campusai.data.remote.EduProbeRequest
import com.example.campusai.data.remote.EduProbeResult
import com.example.campusai.data.remote.EduScheduleItemsResponse
import com.example.campusai.data.remote.EduSyncResult

/** EduRepository — 教务系统连接层仓库，封装所有 edu API 调用。 */
class EduRepository {

    private val api = ApiClient.api

    suspend fun getUniversityId(): Result<String> = runCatching {
        val resp = api.me()
        if (!resp.isSuccessful) throw Exception("获取用户信息失败")
        val uid = resp.body()?.user?.university_id
        if (uid.isNullOrBlank()) throw Exception("请先选择你的大学")
        uid
    }

    suspend fun getBinding(): Result<EduBindingDto?> = runCatching {
        val resp = api.getEduBinding()
        if (resp.isSuccessful) resp.body() else null
    }

    suspend fun unbind(): Result<Unit> = runCatching {
        api.eduUnbind()
        Unit
    }

    suspend fun probePortal(portalUrl: String): Result<EduProbeResult> = runCatching {
        val resp = api.eduProbe(EduProbeRequest(portalUrl))
        if (!resp.isSuccessful) throw Exception(resp.errorBody()?.string() ?: "探测失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun createConnectionFromUrl(portalUrl: String, universityId: String?): Result<EduConnectionDto> = runCatching {
        val resp = api.eduCreateConnectionFromUrl(EduConnectionFromUrlRequest(portalUrl, universityId))
        if (!resp.isSuccessful) throw Exception(resp.errorBody()?.string() ?: "创建连接失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun getConnection(connectionId: String): Result<EduConnectionDto> = runCatching {
        val resp = api.eduGetConnection(connectionId)
        if (!resp.isSuccessful) throw Exception("查询连接失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun continueWithCredentials(connectionId: String, username: String, password: String): Result<EduConnectionDto> = runCatching {
        val resp = api.eduContinueConnection(
            connectionId,
            EduConnectionContinueRequest(username = username, password = password),
        )
        if (!resp.isSuccessful) throw Exception(resp.errorBody()?.string() ?: "登录失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun preLogin(connectionId: String): Result<EduPreLoginResult> = runCatching {
        val resp = api.eduPreLogin(connectionId)
        if (!resp.isSuccessful) throw Exception(resp.errorBody()?.string() ?: "预登录失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun continueWithCaptcha(
        connectionId: String,
        username: String,
        password: String,
        captcha: String,
        preLoginToken: String,
    ): Result<EduConnectionDto> = runCatching {
        val resp = api.eduContinueConnection(
            connectionId,
            EduConnectionContinueRequest(
                username = username,
                password = password,
                captcha = captcha,
                pre_login_token = preLoginToken,
                action = "SUBMIT_WITH_CAPTCHA",
            ),
        )
        if (!resp.isSuccessful) throw Exception(resp.errorBody()?.string() ?: "登录失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun continueWithCookies(
        connectionId: String,
        cookieJar: List<com.example.campusai.data.remote.EduCookieDto>,
        currentUrl: String?,
        userAgent: String?,
    ): Result<EduConnectionDto> = runCatching {
        val resp = api.eduContinueConnection(
            connectionId,
            EduConnectionContinueRequest(
                action = "CLIENT_WEBVIEW_COMPLETE",
                cookie_jar = cookieJar,
                current_url = currentUrl,
                user_agent = userAgent,
            ),
        )
        if (!resp.isSuccessful) throw Exception(resp.errorBody()?.string() ?: "回传 Cookie 失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun pollConnection(connectionId: String): Result<EduConnectionDto> = runCatching {
        val resp = api.eduContinueConnection(connectionId, EduConnectionContinueRequest(action = "POLL"))
        if (!resp.isSuccessful) throw Exception("轮询失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun cancelConnection(connectionId: String): Result<EduConnectionDto> = runCatching {
        val resp = api.eduContinueConnection(connectionId, EduConnectionContinueRequest(action = "CANCEL"))
        if (!resp.isSuccessful) throw Exception("取消失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun syncSchedule(semester: String? = null): Result<EduSyncResult> = runCatching {
        val resp = api.eduSyncSchedule(semester)
        if (!resp.isSuccessful) throw Exception("课表同步失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun syncGrade(semester: String? = null): Result<EduSyncResult> = runCatching {
        val resp = api.eduSyncGrade(semester)
        if (!resp.isSuccessful) throw Exception("成绩同步失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun syncExam(semester: String? = null): Result<EduSyncResult> = runCatching {
        val resp = api.eduSyncExam(semester)
        if (!resp.isSuccessful) throw Exception("考试同步失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun listScheduleSemesters(): Result<List<String>> = runCatching {
        val resp = api.eduScheduleSemesters()
        if (resp.isSuccessful) resp.body() ?: emptyList() else emptyList()
    }

    suspend fun listScheduleItems(semester: String? = null): Result<EduScheduleItemsResponse> = runCatching {
        val resp = api.eduScheduleItems(semester)
        if (!resp.isSuccessful) throw Exception("加载课表失败 (${resp.code()})")
        resp.body()!!
    }

    suspend fun listGradeSemesters(): Result<List<String>> = runCatching {
        val resp = api.eduGradeSemesters()
        if (resp.isSuccessful) resp.body() ?: emptyList() else emptyList()
    }

    suspend fun listGradeItems(semester: String? = null): Result<EduGradeItemsResponse> = runCatching {
        val resp = api.eduGradeItems(semester)
        if (!resp.isSuccessful) throw Exception("加载成绩失败 (${resp.code()})")
        resp.body()!!
    }
}