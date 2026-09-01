package com.example.campusai.ui.screens.dashboard.gamified

import com.example.campusai.data.model.ExamStatus
import com.example.campusai.data.model.FocusMode
import com.example.campusai.features.gamification.AchievementCatalog
import com.example.campusai.features.gamification.CompletedFocusFact
import com.example.campusai.features.gamification.CompletedTaskFact
import com.example.campusai.features.gamification.GamificationEngine
import com.example.campusai.features.gamification.GamificationFacts
import com.example.campusai.features.gamification.LevelCalculator
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

object GamifiedDashboardStateFactory {
    fun create(input: GamifiedDashboardInputs): GamifiedDashboardUiState {
        val facts = facts(input)
        val level = LevelCalculator.calculate(input.snapshot.totalXp)
        val streak = GamificationEngine.calculateStreak(
            facts.completedTasks.map { it.completedAt } + facts.completedFocusSessions.map { it.completedAt },
            input.now,
            input.zoneId,
        )
        val today = input.now.atZone(input.zoneId).toLocalDate()
        val todayTasks = facts.completedTasks.filter { it.completedAt.atZone(input.zoneId).toLocalDate() == today }
        val todayFocusMinutes = facts.completedFocusSessions
            .filter { it.completedAt.atZone(input.zoneId).toLocalDate() == today }
            .sumOf { it.durationMinutes }
        val completedGoals = (if (todayTasks.isNotEmpty()) 1 else 0) + (if (todayFocusMinutes >= 60) 1 else 0)
        val nextReward = when {
            todayTasks.isEmpty() -> 20
            todayFocusMinutes < 60 -> 30
            else -> 0
        }
        val nextExam = input.exams
            .filter { it.statusAt(input.now.toEpochMilli(), input.zoneId) == ExamStatus.UPCOMING }
            .minByOrNull { it.startDateTime() ?: LocalDateTime.MAX }

        val adventure = if (nextExam != null) {
            val days = nextExam.daysUntil(input.now.toEpochMilli(), input.zoneId)
            DailyAdventureUiState(
                title = "期末挑战",
                subtitle = buildString {
                    append(nextExam.courseName)
                    if (days != null) append(" · 距离考试 $days 天")
                },
                completed = completedGoals,
                total = 2,
                progress = completedGoals / 2f,
                nextRewardXp = nextReward,
                route = "exams",
            )
        } else {
            val subtitle = when (completedGoals) {
                2 -> "今日目标全部完成，成长记录已更新"
                else -> "再完成 ${2 - completedGoals} 项，获得 +$nextReward XP"
            }
            DailyAdventureUiState(
                title = "今日冒险",
                subtitle = subtitle,
                completed = completedGoals,
                total = 2,
                progress = completedGoals / 2f,
                nextRewardXp = nextReward,
                route = if (todayTasks.isEmpty()) "tasks" else "focus",
            )
        }

        val questSeeds = buildList {
            nextExam?.let { exam ->
                add(
                    MainQuestUiState(
                        id = "exam-${exam.id}",
                        eyebrow = "FINAL CHALLENGE",
                        title = exam.courseName,
                        meta = "${exam.dateLabel()} · ${exam.startTime}",
                        detail = exam.location,
                        status = exam.type,
                        rewardXp = 0,
                        route = "exams",
                        primary = false,
                    ),
                )
            }
            input.tasks.firstOrNull { !it.done }?.let { task ->
                add(
                    MainQuestUiState(
                        id = "task-${task.id}",
                        eyebrow = "NEXT QUEST",
                        title = task.title,
                        meta = task.due,
                        detail = task.course,
                        status = if (task.importance.equals("high", true) || task.importance.equals("urgent", true)) "高优先级" else "待完成",
                        rewardXp = if (task.importance.equals("high", true) || task.importance.equals("urgent", true)) 30 else 20,
                        route = "tasks",
                        primary = false,
                    ),
                )
            }
            input.courses.firstOrNull()?.let { course ->
                add(
                    MainQuestUiState(
                        id = "course-${course.id.ifBlank { course.name }}",
                        eyebrow = "COURSE PATH",
                        title = course.name,
                        meta = "本学期课程",
                        detail = listOf(course.location, course.teacher).filter(String::isNotBlank).joinToString(" · ").ifBlank { "查看课程详情" },
                        status = course.type.ifBlank { "进行中" },
                        rewardXp = 0,
                        route = "courses",
                        primary = false,
                    ),
                )
            }
        }.mapIndexed { index, quest -> quest.copy(primary = index == 0) }

        val weekStartDate = today.minusDays((today.dayOfWeek.value - 1).toLong())
        val weekStart = weekStartDate.atStartOfDay(input.zoneId).toInstant()
        val weekXp = input.snapshot.events
            .filter { !it.awardedAt.isBefore(weekStart) && !it.awardedAt.isAfter(input.now) }
            .sumOf { it.xp.coerceAtLeast(0) }
        val weekFocus = facts.completedFocusSessions
            .filter { !it.completedAt.isBefore(weekStart) && !it.completedAt.isAfter(input.now) }
            .sumOf { it.durationMinutes }
        val weekTasks = facts.completedTasks.count {
            !it.completedAt.isBefore(weekStart) && !it.completedAt.isAfter(input.now)
        }
        val unlocked = input.snapshot.achievements.associateBy { it.id }
        val totalFocus = facts.completedFocusSessions.sumOf { it.durationMinutes }
        val achievements = AchievementCatalog.definitions.map { definition ->
            val (current, target, unit) = when (definition.id) {
                "first-focus" -> Triple(if (facts.completedFocusSessions.isNotEmpty()) 1 else 0, 1, "次专注")
                "focus-60" -> Triple(totalFocus.coerceAtMost(60), 60, "分钟")
                "focus-600" -> Triple(totalFocus.coerceAtMost(600), 600, "分钟")
                "task-hunter-50" -> Triple(facts.completedTasks.size.coerceAtMost(50), 50, "项任务")
                "streak-7" -> Triple(streak.coerceAtMost(7), 7, "天连续")
                else -> Triple(0, 1, "项")
            }
            val unlock = unlocked[definition.id]
            AchievementUiState(
                id = definition.id,
                title = definition.title,
                description = definition.description,
                unlocked = unlock != null,
                unlockedAtLabel = unlock?.unlockedAt?.atZone(input.zoneId)?.toLocalDate()?.format(DateTimeFormatter.ofPattern("M月d日")) ?: "",
                current = current,
                target = target,
                unit = unit,
            )
        }

        return GamifiedDashboardUiState(
            player = PlayerUiState(
                name = input.user?.name?.takeIf(String::isNotBlank) ?: "同学",
                level = level.currentLevel,
                title = LevelCalculator.titleFor(level.currentLevel),
                totalXp = level.totalXp,
                currentXp = level.currentXp,
                nextLevelXp = level.nextLevelXp,
                progress = level.progress,
                streakDays = streak,
            ),
            adventure = adventure,
            mainQuests = questSeeds,
            mainQuestEmptyMessage = if (questSeeds.isEmpty()) "暂无主线任务，去添加一个真实待办吧" else null,
            sideQuests = sideQuests,
            growth = GrowthUiState(weekXp, weekFocus, weekTasks, streak),
            achievements = achievements,
            campusWorld = input.campusNews.take(3).map { news ->
                CampusWorldUiState(news.id, news.title, news.summary, news.category, "campus-news-detail/${news.id}")
            },
            isLoading = input.examsLoading || input.focusLoading,
            messages = listOfNotNull(input.taskError, input.focusError).distinct(),
            reduceMotion = input.reduceMotion,
        )
    }

    fun facts(input: GamifiedDashboardInputs): GamificationFacts = GamificationFacts(
        completedTasks = input.tasks.mapNotNull { task ->
            if (!task.done) return@mapNotNull null
            val completedAt = task.completedAt?.let { parseTimestamp(it, input.zoneId) } ?: return@mapNotNull null
            CompletedTaskFact(task.id, task.importance, completedAt)
        },
        completedFocusSessions = input.focusRecords.mapNotNull { record ->
            if (!record.finished || record.mode != FocusMode.FOCUS.name || record.actualMinutes <= 0) return@mapNotNull null
            val completedAt = runCatching {
                LocalDate.parse(record.date)
                    .atTime(LocalTime.parse(record.endedAt))
                    .atZone(input.zoneId)
                    .toInstant()
            }.getOrNull() ?: return@mapNotNull null
            CompletedFocusFact(record.sourceId, record.actualMinutes, completedAt)
        },
    )

    private fun parseTimestamp(value: String, zoneId: ZoneId): Instant? =
        runCatching { Instant.parse(value) }.getOrNull()
            ?: runCatching { OffsetDateTime.parse(value).toInstant() }.getOrNull()
            ?: runCatching { LocalDateTime.parse(value).atZone(zoneId).toInstant() }.getOrNull()

    private val sideQuests = listOf(
        SideQuestUiState("专注自习", "开启一段真实专注", "focus"),
        SideQuestUiState("AI 导员", "规划下一步行动", "counselor"),
        SideQuestUiState("空教室", "寻找安静学习地点", "classrooms"),
        SideQuestUiState("办事大厅", "处理校园事务", "services"),
        SideQuestUiState("失物招领", "发现与归还物品", "lostfound"),
        SideQuestUiState("考试安排", "查看下一场挑战", "exams"),
    )
}
