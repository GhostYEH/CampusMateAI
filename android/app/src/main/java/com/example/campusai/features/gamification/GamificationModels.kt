package com.example.campusai.features.gamification

import java.time.Instant

enum class DashboardStyle(val storedValue: String) {
    CLASSIC("classic"),
    GAMIFIED("gamified"),
    IMMERSIVE("immersive");

    companion object {
        fun fromStoredValue(value: String?): DashboardStyle =
            entries.firstOrNull { it.storedValue.equals(value?.trim(), ignoreCase = true) } ?: CLASSIC
    }
}

enum class XpSourceType {
    TASK,
    FOCUS_SESSION,
    DAILY_GOAL,
}

enum class XpEventType {
    TASK_COMPLETED,
    FOCUS_SESSION_COMPLETED,
    DAILY_TASK_GOAL,
    DAILY_FOCUS_GOAL,
}

data class XpEvent(
    val eventType: XpEventType,
    val sourceType: XpSourceType,
    val sourceId: String,
    val xp: Int,
    val awardedAt: Instant,
) {
    val id: String get() = "${eventType.name}:${sourceType.name}:$sourceId"
}

data class AchievementUnlock(
    val id: String,
    val unlockedAt: Instant,
)

data class GamificationSnapshot(
    val version: Int = CURRENT_VERSION,
    val events: List<XpEvent> = emptyList(),
    val achievements: List<AchievementUnlock> = emptyList(),
) {
    val totalXp: Int get() = events.sumOf { it.xp.coerceAtLeast(0) }

    companion object {
        const val CURRENT_VERSION = 1
    }
}

data class CompletedTaskFact(
    val id: String,
    val importance: String,
    val completedAt: Instant,
)

data class CompletedFocusFact(
    val id: String,
    val durationMinutes: Int,
    val completedAt: Instant,
)

data class GamificationFacts(
    val completedTasks: List<CompletedTaskFact> = emptyList(),
    val completedFocusSessions: List<CompletedFocusFact> = emptyList(),
)

data class DailyQuest(
    val id: String,
    val title: String,
    val completed: Boolean,
    val rewardXp: Int,
)

data class AchievementDefinition(
    val id: String,
    val title: String,
    val description: String,
)

object AchievementCatalog {
    val definitions = listOf(
        AchievementDefinition("first-focus", "初心者", "完成第一次专注"),
        AchievementDefinition("focus-60", "专注起航", "累计专注 60 分钟"),
        AchievementDefinition("focus-600", "学习达人", "累计专注 10 小时"),
        AchievementDefinition("task-hunter-50", "任务猎人", "完成 50 个个人待办"),
        AchievementDefinition("streak-7", "坚持不懈", "连续学习 7 天"),
    )
}

data class LevelProgress(
    val currentLevel: Int,
    val totalXp: Int,
    val currentXp: Int,
    val nextLevelXp: Int,
    val progress: Float,
)
