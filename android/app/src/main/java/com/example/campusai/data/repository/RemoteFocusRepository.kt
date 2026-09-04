package com.example.campusai.data.repository

import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusSessionMode
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.FocusStats
import com.example.campusai.data.model.FocusBehaviorSummary
import java.time.Instant
import java.time.Duration
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

data class StudySessionSnapshot(
    val id: String,
    val relatedTaskId: String? = null,
    val startedAt: String,
    val endedAt: String?,
    val plannedDurationSeconds: Int = 0,
    val durationSeconds: Int,
    val status: String,
    val mode: FocusMode,
    val sessionMode: FocusSessionMode = FocusSessionMode.QUIET,
    val pausedAt: String? = null,
    val pauseSeconds: Int = 0,
    val behaviorSummary: FocusBehaviorSummary? = null,
)

/**
 * The backend session is the single source of truth for the countdown.  This
 * lets the timer continue correctly when the user switches between screens.
 */
fun StudySessionSnapshot.remainingSeconds(now: Instant = Instant.now()): Int {
    if (status == "completed") return 0
    val started = runCatching { Instant.parse(startedAt) }.getOrNull() ?: return mode.totalSeconds
    val openPauseSeconds = if (status == "paused") {
        pausedAt?.let { paused ->
            runCatching { Duration.between(Instant.parse(paused), now).seconds }.getOrDefault(0)
        } ?: 0
    } else 0
    val elapsedSeconds = Duration.between(started, now).seconds - pauseSeconds - openPauseSeconds
    val plannedSeconds = plannedDurationSeconds.takeIf { it > 0 } ?: mode.totalSeconds
    return (plannedSeconds.toLong() - elapsedSeconds).coerceIn(0, plannedSeconds.toLong()).toInt()
}

class RemoteFocusRepository(
    sessions: List<StudySessionSnapshot>,
    goalMinutes: Int,
    private val now: () -> Instant = { Instant.now() },
) {
    private val completed = sessions.filter { it.status == "completed" }

    val records: List<FocusRecord> = completed.mapIndexed { index, session ->
        val ended = session.endedAt?.let(Instant::parse) ?: now()
        FocusRecord(
            id = index.toLong(),
            date = ended.atZone(ZoneId.systemDefault()).toLocalDate().toString(),
            mode = session.mode.name,
            plannedMinutes = session.mode.minutes,
            actualMinutes = (session.durationSeconds / 60).coerceAtLeast(0),
            finished = true,
            endedAt = ended.atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("HH:mm")),
            sourceId = session.id,
            behaviorSummary = session.behaviorSummary,
        )
    }

    val stats: FocusStats = deriveStats(records, goalMinutes, now)

    private fun deriveStats(
        records: List<FocusRecord>,
        goalMinutes: Int,
        now: () -> Instant,
    ): FocusStats {
        val today = now().atZone(ZoneId.systemDefault()).toLocalDate()
        val focusRecords = records.filter { it.mode == FocusMode.FOCUS.name }
        val dates = focusRecords.map { LocalDate.parse(it.date) }.toSet()
        var streak = 0
        var cursor = if (today in dates) today else today.minusDays(1)
        while (cursor in dates) {
            streak++
            cursor = cursor.minusDays(1)
        }
        val todayRecords = focusRecords.filter { it.date == today.toString() }
        return FocusStats(
            todayMinutes = todayRecords.sumOf { it.actualMinutes },
            todayCount = todayRecords.size,
            streakDays = streak,
            goalMinutes = goalMinutes,
        )
    }
}
