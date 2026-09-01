package com.example.campusai.ui.screens.dashboard.gamified

import androidx.compose.runtime.Immutable
import com.example.campusai.data.model.CampusNews
import com.example.campusai.data.model.Course
import com.example.campusai.data.model.Exam
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.Task
import com.example.campusai.data.model.User
import com.example.campusai.features.gamification.GamificationSnapshot
import java.time.Instant
import java.time.ZoneId

@Immutable
data class PlayerUiState(
    val name: String = "同学",
    val level: Int = 1,
    val title: String = "校园新旅人",
    val totalXp: Int = 0,
    val currentXp: Int = 0,
    val nextLevelXp: Int = 100,
    val progress: Float = 0f,
    val streakDays: Int = 0,
)

@Immutable
data class DailyAdventureUiState(
    val title: String = "今日冒险",
    val subtitle: String = "完成一项真实任务，开始今天的成长",
    val completed: Int = 0,
    val total: Int = 2,
    val progress: Float = 0f,
    val nextRewardXp: Int = 20,
    val route: String = "tasks",
)

@Immutable
data class MainQuestUiState(
    val id: String,
    val eyebrow: String,
    val title: String,
    val meta: String,
    val detail: String,
    val status: String,
    val rewardXp: Int,
    val route: String,
    val primary: Boolean,
)

@Immutable
data class SideQuestUiState(
    val title: String,
    val description: String,
    val route: String,
)

@Immutable
data class GrowthUiState(
    val weekXp: Int = 0,
    val weekFocusMinutes: Int = 0,
    val weekCompletedTasks: Int = 0,
    val streakDays: Int = 0,
)

@Immutable
data class AchievementUiState(
    val id: String,
    val title: String,
    val description: String,
    val unlocked: Boolean,
    val unlockedAtLabel: String,
    val current: Int,
    val target: Int,
    val unit: String,
)

@Immutable
data class CampusWorldUiState(
    val id: String,
    val title: String,
    val summary: String,
    val category: String,
    val route: String,
)

@Immutable
data class GamifiedDashboardUiState(
    val player: PlayerUiState = PlayerUiState(),
    val adventure: DailyAdventureUiState = DailyAdventureUiState(),
    val mainQuests: List<MainQuestUiState> = emptyList(),
    val mainQuestEmptyMessage: String? = "暂无主线任务，去添加一个真实待办吧",
    val sideQuests: List<SideQuestUiState> = emptyList(),
    val growth: GrowthUiState = GrowthUiState(),
    val achievements: List<AchievementUiState> = emptyList(),
    val campusWorld: List<CampusWorldUiState> = emptyList(),
    val isLoading: Boolean = true,
    val messages: List<String> = emptyList(),
    val reduceMotion: Boolean = false,
)

data class GamifiedDashboardInputs(
    val user: User? = null,
    val tasks: List<Task> = emptyList(),
    val courses: List<Course> = emptyList(),
    val campusNews: List<CampusNews> = emptyList(),
    val exams: List<Exam> = emptyList(),
    val focusRecords: List<FocusRecord> = emptyList(),
    val snapshot: GamificationSnapshot = GamificationSnapshot(),
    val examsLoading: Boolean = false,
    val focusLoading: Boolean = false,
    val taskError: String? = null,
    val focusError: String? = null,
    val reduceMotion: Boolean = false,
    val now: Instant = Instant.now(),
    val zoneId: ZoneId = ZoneId.systemDefault(),
)
