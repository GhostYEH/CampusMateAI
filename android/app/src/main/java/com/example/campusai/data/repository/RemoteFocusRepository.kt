package com.example.campusai.data.repository

import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.FocusStats
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

data class StudySessionSnapshot(
    val id: String,
    val startedAt: String,
    val endedAt: String?,
    val durationSeconds: Int,
    val status: String,
    val mode: FocusMode,
)

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
