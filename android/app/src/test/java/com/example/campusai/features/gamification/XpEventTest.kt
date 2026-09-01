package com.example.campusai.features.gamification

import java.time.Instant
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class XpEventTest {
    private val zone = ZoneId.of("Asia/Shanghai")
    private val now = Instant.parse("2026-08-31T04:00:00Z")

    @Test
    fun reconciliationAwardsRealSourcesOnce() {
        val facts = GamificationFacts(
            completedTasks = listOf(
                CompletedTaskFact("task-high", "high", Instant.parse("2026-08-31T00:30:00Z")),
                CompletedTaskFact("task-normal", "normal", Instant.parse("2026-08-30T01:00:00Z")),
            ),
            completedFocusSessions = listOf(
                CompletedFocusFact("focus-25", 25, Instant.parse("2026-08-31T02:00:00Z")),
                CompletedFocusFact("focus-short", 20, Instant.parse("2026-08-31T03:00:00Z")),
            ),
        )

        val first = GamificationEngine.reconcile(GamificationSnapshot(), facts, now, zone)
        assertEquals(
            listOf(
                "TASK_COMPLETED:TASK:task-high" to 30,
                "TASK_COMPLETED:TASK:task-normal" to 20,
                "FOCUS_SESSION_COMPLETED:FOCUS_SESSION:focus-25" to 15,
                "DAILY_TASK_GOAL:DAILY_GOAL:2026-08-31" to 20,
            ),
            first.events.map { it.id to it.xp },
        )
        assertEquals(85, first.totalXp)

        val second = GamificationEngine.reconcile(first, facts, now, zone)
        assertEquals(first.events, second.events)
        assertEquals(85, second.totalXp)
    }

    @Test
    fun sixtyRealFocusMinutesEarnsSessionAndDailyRewardsOnce() {
        val facts = GamificationFacts(
            completedFocusSessions = listOf(
                CompletedFocusFact("focus-a", 25, Instant.parse("2026-08-31T01:00:00Z")),
                CompletedFocusFact("focus-b", 35, Instant.parse("2026-08-31T02:00:00Z")),
            ),
        )

        val snapshot = GamificationEngine.reconcile(GamificationSnapshot(), facts, now, zone)
        assertEquals(
            listOf(
                "FOCUS_SESSION_COMPLETED:FOCUS_SESSION:focus-a",
                "FOCUS_SESSION_COMPLETED:FOCUS_SESSION:focus-b",
                "DAILY_FOCUS_GOAL:DAILY_GOAL:2026-08-31",
            ),
            snapshot.events.map(XpEvent::id),
        )
        assertEquals(60, snapshot.totalXp)
    }

    @Test
    fun streakUsesOnlyTimestampedTaskAndFocusActivity() {
        val activity = listOf(
            Instant.parse("2026-08-28T01:00:00Z"),
            Instant.parse("2026-08-29T01:00:00Z"),
            Instant.parse("2026-08-30T01:00:00Z"),
        )
        assertEquals(3, GamificationEngine.calculateStreak(activity, now, zone))
        assertEquals(0, GamificationEngine.calculateStreak(emptyList(), now, zone))
    }

    @Test
    fun achievementsUnlockOnceFromRealFacts() {
        val taskFacts = (0 until 50).map { index ->
            CompletedTaskFact(
                id = "task-$index",
                importance = "normal",
                completedAt = Instant.parse("2026-08-${25 + index % 7}T00:00:00Z"),
            )
        }
        val facts = GamificationFacts(
            completedTasks = taskFacts,
            completedFocusSessions = listOf(
                CompletedFocusFact("focus-long", 600, Instant.parse("2026-08-31T02:00:00Z")),
            ),
        )

        val first = AchievementEvaluator.evaluate(emptyList(), facts, now, zone)
        assertEquals(
            listOf("first-focus", "focus-60", "focus-600", "task-hunter-50", "streak-7"),
            first.map(AchievementUnlock::id),
        )

        val second = AchievementEvaluator.evaluate(first, facts, now.plusSeconds(86_400), zone)
        assertEquals(first, second)
        assertTrue(second.all { it.unlockedAt == now })
    }
}
