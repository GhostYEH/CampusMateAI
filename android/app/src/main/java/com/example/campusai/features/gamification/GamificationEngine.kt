package com.example.campusai.features.gamification

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

object GamificationEngine {
    fun reconcile(
        snapshot: GamificationSnapshot,
        facts: GamificationFacts,
        now: Instant = Instant.now(),
        zoneId: ZoneId = ZoneId.systemDefault(),
    ): GamificationSnapshot {
        val events = snapshot.events.toMutableList()
        val knownIds = events.mapTo(mutableSetOf()) { it.id }

        fun append(event: XpEvent) {
            if (knownIds.add(event.id)) events += event
        }

        facts.completedTasks.forEach { task ->
            append(
                XpEvent(
                    eventType = XpEventType.TASK_COMPLETED,
                    sourceType = XpSourceType.TASK,
                    sourceId = task.id,
                    xp = if (task.importance.equals("high", true) || task.importance.equals("urgent", true)) 30 else 20,
                    awardedAt = task.completedAt,
                ),
            )
        }

        facts.completedFocusSessions
            .filter { it.durationMinutes >= 25 }
            .forEach { focus ->
                append(
                    XpEvent(
                        eventType = XpEventType.FOCUS_SESSION_COMPLETED,
                        sourceType = XpSourceType.FOCUS_SESSION,
                        sourceId = focus.id,
                        xp = 15,
                        awardedAt = focus.completedAt,
                    ),
                )
            }

        val today = now.atZone(zoneId).toLocalDate()
        if (facts.completedTasks.any { it.completedAt.atZone(zoneId).toLocalDate() == today }) {
            append(
                XpEvent(
                    eventType = XpEventType.DAILY_TASK_GOAL,
                    sourceType = XpSourceType.DAILY_GOAL,
                    sourceId = today.toString(),
                    xp = 20,
                    awardedAt = now,
                ),
            )
        }

        val todayFocusMinutes = facts.completedFocusSessions
            .filter { it.completedAt.atZone(zoneId).toLocalDate() == today }
            .sumOf { it.durationMinutes.coerceAtLeast(0) }
        if (todayFocusMinutes >= 60) {
            append(
                XpEvent(
                    eventType = XpEventType.DAILY_FOCUS_GOAL,
                    sourceType = XpSourceType.DAILY_GOAL,
                    sourceId = today.toString(),
                    xp = 30,
                    awardedAt = now,
                ),
            )
        }

        return GamificationSnapshot(
            events = events,
            achievements = AchievementEvaluator.evaluate(snapshot.achievements, facts, now, zoneId),
        )
    }

    fun calculateStreak(
        activity: List<Instant>,
        now: Instant = Instant.now(),
        zoneId: ZoneId = ZoneId.systemDefault(),
    ): Int {
        val dates = activity.mapTo(mutableSetOf()) { it.atZone(zoneId).toLocalDate() }
        if (dates.isEmpty()) return 0
        val today = now.atZone(zoneId).toLocalDate()
        var cursor: LocalDate = if (today in dates) today else today.minusDays(1)
        var streak = 0
        while (cursor in dates) {
            streak += 1
            cursor = cursor.minusDays(1)
        }
        return streak
    }
}

object AchievementEvaluator {
    fun evaluate(
        previous: List<AchievementUnlock>,
        facts: GamificationFacts,
        now: Instant = Instant.now(),
        zoneId: ZoneId = ZoneId.systemDefault(),
    ): List<AchievementUnlock> {
        val achievements = previous.toMutableList()
        val unlockedIds = achievements.mapTo(mutableSetOf()) { it.id }
        val focusMinutes = facts.completedFocusSessions.sumOf { it.durationMinutes.coerceAtLeast(0) }
        val streak = GamificationEngine.calculateStreak(
            activity = facts.completedTasks.map { it.completedAt } + facts.completedFocusSessions.map { it.completedAt },
            now = now,
            zoneId = zoneId,
        )
        val qualifies = mapOf(
            "first-focus" to facts.completedFocusSessions.isNotEmpty(),
            "focus-60" to (focusMinutes >= 60),
            "focus-600" to (focusMinutes >= 600),
            "task-hunter-50" to (facts.completedTasks.size >= 50),
            "streak-7" to (streak >= 7),
        )

        AchievementCatalog.definitions.forEach { definition ->
            if (qualifies[definition.id] == true && unlockedIds.add(definition.id)) {
                achievements += AchievementUnlock(definition.id, now)
            }
        }
        return achievements
    }
}
