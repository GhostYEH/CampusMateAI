package com.example.campusai.ui.screens.dashboard.gamified

import com.example.campusai.data.model.CampusNews
import com.example.campusai.data.model.Course
import com.example.campusai.data.model.Exam
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.Task
import com.example.campusai.data.model.User
import com.example.campusai.features.gamification.AchievementUnlock
import com.example.campusai.features.gamification.GamificationSnapshot
import com.example.campusai.features.gamification.XpEvent
import com.example.campusai.features.gamification.XpEventType
import com.example.campusai.features.gamification.XpSourceType
import java.time.Instant
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GamifiedDashboardStateFactoryTest {
    private val now = Instant.parse("2026-09-01T02:00:00Z")
    private val zone = ZoneId.of("Asia/Shanghai")

    @Test
    fun emptyInputsProduceHonestActionableState() {
        val state = GamifiedDashboardStateFactory.create(
            GamifiedDashboardInputs(now = now, zoneId = zone),
        )

        assertEquals("同学", state.player.name)
        assertEquals(1, state.player.level)
        assertEquals("今日冒险", state.adventure.title)
        assertEquals(0, state.adventure.completed)
        assertEquals(2, state.adventure.total)
        assertTrue(state.mainQuests.isEmpty())
        assertNotNull(state.mainQuestEmptyMessage)
        assertEquals(
            listOf("focus", "counselor", "classrooms", "services", "lostfound", "exams"),
            state.sideQuests.map(SideQuestUiState::route),
        )
        assertTrue(state.campusWorld.isEmpty())
    }

    @Test
    fun upcomingExamOverridesAdventureAndRealItemsBecomeQuests() {
        val exam = Exam(
            id = 9,
            courseName = "数据结构与算法设计实践（荣誉课程）",
            date = "2026-09-04",
            startTime = "09:00",
            endTime = "11:00",
            location = "博学楼 1-401",
            seatNumber = "18",
            type = "期末考试",
        )
        val state = GamifiedDashboardStateFactory.create(
            GamifiedDashboardInputs(
                user = User("林知夏", "student", "计算机科学与技术"),
                tasks = listOf(Task("task-1", "算法作业与复杂度分析报告终稿", "今天 23:59", "数据结构", false, importance = "high")),
                courses = listOf(Course("course-1", "计算机网络协议分析与工程实践", teacher = "周老师", location = "实验楼 B-310")),
                exams = listOf(exam),
                now = now,
                zoneId = zone,
            ),
        )

        assertEquals("期末挑战", state.adventure.title)
        assertTrue(state.adventure.subtitle.contains("数据结构与算法设计实践"))
        assertTrue(state.adventure.subtitle.contains("3 天"))
        assertEquals("exams", state.adventure.route)
        assertEquals("数据结构与算法设计实践（荣誉课程）", state.mainQuests.first().title)
        assertEquals(listOf("exams", "tasks", "courses"), state.mainQuests.map(MainQuestUiState::route))
        assertEquals(30, state.mainQuests[1].rewardXp)
    }

    @Test
    fun realActivityDrivesPlayerGrowthAndAchievementProgress() {
        val snapshot = GamificationSnapshot(
            events = listOf(
                XpEvent(XpEventType.TASK_COMPLETED, XpSourceType.TASK, "task-1", 30, Instant.parse("2026-09-01T00:00:00Z")),
                XpEvent(XpEventType.FOCUS_SESSION_COMPLETED, XpSourceType.FOCUS_SESSION, "focus-1", 15, Instant.parse("2026-09-01T01:00:00Z")),
                XpEvent(XpEventType.DAILY_TASK_GOAL, XpSourceType.DAILY_GOAL, "2026-09-01", 20, now),
            ),
            achievements = listOf(AchievementUnlock("first-focus", now)),
        )
        val state = GamifiedDashboardStateFactory.create(
            GamifiedDashboardInputs(
                tasks = listOf(Task("task-1", "完成实验", "今天", "课程作业", true, importance = "high", completedAt = "2026-09-01T00:00:00Z")),
                focusRecords = listOf(FocusRecord(1, "2026-09-01", "FOCUS", 25, 25, true, "09:00", sourceId = "focus-1")),
                snapshot = snapshot,
                now = now,
                zoneId = zone,
            ),
        )

        assertEquals(65, state.player.totalXp)
        assertEquals(65, state.growth.weekXp)
        assertEquals(25, state.growth.weekFocusMinutes)
        assertEquals(1, state.growth.weekCompletedTasks)
        assertEquals(1, state.growth.streakDays)
        assertEquals(1, state.adventure.completed)
        assertEquals(30, state.adventure.nextRewardXp)
        assertTrue(state.achievements.first { it.id == "first-focus" }.unlocked)
        assertEquals(25, state.achievements.first { it.id == "focus-60" }.current)
    }

    @Test
    fun loadingAndErrorsRemainVisibleWithoutHidingCachedContent() {
        val state = GamifiedDashboardStateFactory.create(
            GamifiedDashboardInputs(
                campusNews = listOf(CampusNews("n1", "图书馆延时开放", "考试周开放至 22:00", "详情", "图书馆", "今天")),
                examsLoading = true,
                focusLoading = true,
                taskError = "待办数据加载失败，请稍后重试",
                focusError = "专注记录暂时不可用",
                now = now,
                zoneId = zone,
            ),
        )

        assertTrue(state.isLoading)
        assertEquals(2, state.messages.size)
        assertEquals(1, state.campusWorld.size)
        assertFalse(state.campusWorld.first().title.isBlank())
    }
}
