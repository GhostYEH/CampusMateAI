package com.example.campusai.data.repository

import android.app.Application
import com.example.campusai.data.local.AppDataStore
import com.example.campusai.data.remote.ApiClient

/**
 * 五个新模块（考试 / 空教室 / 办事大厅 / 专注 / 失物招领）的仓库集合。
 * 当前全部为本地实现，后端接口就绪后可在 Application 层整体替换为 Remote 实现。
 */
class ModuleRepositories(
    val exams: ExamRepository,
    val classrooms: ClassroomRepository,
    val services: ServiceRepository,
    val focus: ApiFocusRepository,
    val focusPlans: FocusPlanRepository,
    val lostFound: LostFoundRepository,
    val community: CommunityRepository,
) {
    companion object {
        fun create(application: Application, appRepository: AppRepository): ModuleRepositories {
            val storage = AppDataStore(application)
            return ModuleRepositories(
                exams = LocalExamRepository(
                    storage = storage,
                    courseNames = { appRepository.courses.value.map { it.name } },
                ),
                classrooms = LocalClassroomRepository(),
                services = LocalServiceRepository(storage),
                focus = ApiFocusRepository(ApiClient.api),
                focusPlans = FocusPlanRepository(
                    storage = storage,
                    api = ApiClient.api,
                    accountKey = {
                        appRepository.session.value?.accountId
                            ?.ifBlank { null }
                            ?: appRepository.session.value?.studentId
                            ?: "anonymous"
                    },
                ),
                lostFound = LocalLostFoundRepository(storage),
                community = CommunityRepository(),
            )
        }
    }
}
