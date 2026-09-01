package com.example.campusai.ui.screens.dashboard.gamified

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.model.CampusNews
import com.example.campusai.data.model.Course
import com.example.campusai.data.model.Exam
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.Task
import com.example.campusai.data.model.User
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ExamRepository
import com.example.campusai.features.gamification.GamificationSnapshot
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class GamifiedDashboardViewModel(
    private val repository: AppRepository,
    private val examRepository: ExamRepository,
    private val focusRepository: ApiFocusRepository,
) : ViewModel() {
    private data class AppData(
        val user: User?,
        val tasks: List<Task>,
        val courses: List<Course>,
        val news: List<CampusNews>,
        val taskError: String?,
    )

    private data class ModuleData(
        val exams: List<Exam>,
        val examsLoading: Boolean,
        val focusRecords: List<FocusRecord>,
        val focusLoading: Boolean,
        val focusError: String?,
    )

    private data class PreferenceData(
        val snapshot: GamificationSnapshot,
        val reduceMotion: Boolean,
    )

    private val appData = combine(
        repository.session,
        repository.tasks,
        repository.courses,
        repository.campusNews,
        repository.taskError,
    ) { user, tasks, courses, news, taskError ->
        AppData(user, tasks, courses, news, taskError)
    }

    private val moduleData = combine(
        examRepository.exams,
        examRepository.loading,
        focusRepository.records,
        focusRepository.loading,
        focusRepository.error,
    ) { exams, examsLoading, focusRecords, focusLoading, focusError ->
        ModuleData(exams, examsLoading, focusRecords, focusLoading, focusError)
    }

    private val preferenceData = combine(
        repository.gamificationStore.snapshot,
        repository.reduceMotion,
    ) { snapshot, reduceMotion -> PreferenceData(snapshot, reduceMotion) }

    val state = combine(appData, moduleData, preferenceData) { app, modules, preference ->
        GamifiedDashboardStateFactory.create(
            GamifiedDashboardInputs(
                user = app.user,
                tasks = app.tasks,
                courses = app.courses,
                campusNews = app.news,
                exams = modules.exams,
                focusRecords = modules.focusRecords,
                snapshot = preference.snapshot,
                examsLoading = modules.examsLoading,
                focusLoading = modules.focusLoading,
                taskError = app.taskError,
                focusError = modules.focusError,
                reduceMotion = preference.reduceMotion,
            ),
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), GamifiedDashboardUiState())

    init {
        combine(repository.tasks, focusRepository.records) { tasks, records ->
            GamifiedDashboardStateFactory.facts(
                GamifiedDashboardInputs(tasks = tasks, focusRecords = records),
            )
        }
            .distinctUntilChanged()
            .onEach(repository.gamificationStore::reconcile)
            .launchIn(viewModelScope)

        viewModelScope.launch {
            listOf(
                async { repository.refreshNotices() },
                async { repository.refreshCampusNews() },
                async { repository.refreshCourses() },
                async { repository.refreshTasks() },
                async { repository.refreshHomeBanners() },
                async { examRepository.refresh() },
                async { focusRepository.refresh() },
            ).awaitAll()
        }
    }

    companion object {
        fun factory(
            repository: AppRepository,
            examRepository: ExamRepository,
            focusRepository: ApiFocusRepository,
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                require(modelClass.isAssignableFrom(GamifiedDashboardViewModel::class.java))
                return GamifiedDashboardViewModel(repository, examRepository, focusRepository) as T
            }
        }
    }
}
