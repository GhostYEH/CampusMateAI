package com.example.campusai.data.repository

import android.app.Application
import com.example.campusai.data.local.AppDataStore
import com.example.campusai.data.remote.ApiClient

/**
 * 保持各端核心模块仓库的统一装配入口。
 * 当前全部为本地实现，后端接口就绪后可在 Application 层整体替换为 Remote 实现。
 */
class ModuleRepositories(
    val exams: ExamRepository,
    val focus: ApiFocusRepository,
    val focusPlans: FocusPlanRepository,
    val community: CommunityRepository,
    val agentRuntime: AgentRuntimeRepository,
    val finalReview: FinalReviewRepository,
    val courseResearch: CourseResearchRepository,
    val noticeWorkflow: NoticeWorkflowRepository,
) {
    companion object {
        fun create(application: Application, appRepository: AppRepository): ModuleRepositories {
            val storage = AppDataStore(application)
            val userIdProvider: () -> String = {
                appRepository.session.value?.accountId
                    ?.ifBlank { null }
                    ?: appRepository.session.value?.studentId
                    ?: "anonymous"
            }
            return ModuleRepositories(
                exams = LocalExamRepository(
                    storage = storage,
                    courseNames = { appRepository.courses.value.map { it.name } },
                ),
                focus = ApiFocusRepository(ApiClient.api),
                focusPlans = FocusPlanRepository(
                    storage = storage,
                    api = ApiClient.api,
                    accountKey = userIdProvider,
                ),
                community = CommunityRepository(),
                agentRuntime = AgentRuntimeRepository(
                    api = ApiClient.api,
                    sseClient = ApiClient.agentSse,
                    userIdProvider = userIdProvider,
                ),
                finalReview = FinalReviewRepository(
                    api = ApiClient.api,
                    sseClient = ApiClient.agentSse,
                    userIdProvider = userIdProvider,
                ),
                courseResearch = CourseResearchRepository(
                    api = ApiClient.api,
                    sseClient = ApiClient.agentSse,
                    userIdProvider = userIdProvider,
                ),
                noticeWorkflow = NoticeWorkflowRepository(
                    api = ApiClient.api,
                    userIdProvider = userIdProvider,
                ),
            )
        }
    }
}
