package com.example.campusai.data.behavior

import com.example.campusai.data.focus.FocusState

enum class FocusSupervisionEventType {
    PHONE_DISTRACTION,
    LONG_LOOK_AWAY,
    PEN_FIDGETING,
    DROWSINESS,
    SLEEPING,
    STUDENT_ABSENT,
    FOCUS_RECOVERED,
    POSSIBLE_DISTRACTION
}

data class FocusSupervisionEvent(
    val type: FocusSupervisionEventType,
    val startedAt: Long,
    val durationMs: Long,
    val confidence: Float?,
    val occurrenceCount: Int
)

data class FocusBehaviorStats(
    var readingDuration: Long = 0,
    var writingDuration: Long = 0,
    var typingDuration: Long = 0,

    var phoneUseCount: Int = 0,
    var phoneUseDuration: Long = 0,

    var penSpinningCount: Int = 0,
    var penSpinningDuration: Long = 0,

    var lookingAwayCount: Int = 0,
    var lookingAwayDuration: Long = 0,

    var drowsyCount: Int = 0,
    var drowsyDuration: Long = 0,

    var absentCount: Int = 0,
    var absentDuration: Long = 0
)

class FocusSupervisor {
    val stats = FocusBehaviorStats()
    private val eventHistory = mutableListOf<FocusSupervisionEvent>()

    fun processEvents(events: List<StableBehaviorEvent>, timestampMs: Long): FocusState {
        var derivedState = FocusState.FOCUSED

        events.forEach { event ->
            when (event) {
                StableBehaviorEvent.STUDENT_ABSENT -> {
                    derivedState = FocusState.NO_FACE
                    stats.absentCount++
                    recordEvent(FocusSupervisionEventType.STUDENT_ABSENT, timestampMs)
                }
                StableBehaviorEvent.PHONE_DISTRACTION -> {
                    derivedState = FocusState.BREAK_SUGGESTED
                    stats.phoneUseCount++
                    recordEvent(FocusSupervisionEventType.PHONE_DISTRACTION, timestampMs)
                }
                StableBehaviorEvent.POSSIBLE_DISTRACTION -> {
                    derivedState = FocusState.POSSIBLY_DISTRACTED
                    recordEvent(FocusSupervisionEventType.POSSIBLE_DISTRACTION, timestampMs)
                }
                StableBehaviorEvent.LONG_LOOK_AWAY -> {
                    if (derivedState == FocusState.FOCUSED) {
                        derivedState = FocusState.POSSIBLY_DISTRACTED
                    }
                    stats.lookingAwayCount++
                    recordEvent(FocusSupervisionEventType.LONG_LOOK_AWAY, timestampMs)
                }
                StableBehaviorEvent.PEN_FIDGETING -> {
                    stats.penSpinningCount++
                    recordEvent(FocusSupervisionEventType.PEN_FIDGETING, timestampMs)
                }
                StableBehaviorEvent.DROWSINESS -> {
                    derivedState = FocusState.POSSIBLY_DISTRACTED
                    stats.drowsyCount++
                    recordEvent(FocusSupervisionEventType.DROWSINESS, timestampMs)
                }
                StableBehaviorEvent.SLEEPING -> {
                    derivedState = FocusState.BREAK_SUGGESTED
                    stats.drowsyCount++
                    recordEvent(FocusSupervisionEventType.SLEEPING, timestampMs)
                }
                StableBehaviorEvent.FOCUS_RECOVERED -> {
                    derivedState = FocusState.FOCUSED
                    recordEvent(FocusSupervisionEventType.FOCUS_RECOVERED, timestampMs)
                }
                StableBehaviorEvent.STABLE_LEARNING -> {
                    derivedState = FocusState.FOCUSED
                }
            }
        }
        
        return derivedState
    }

    private fun recordEvent(type: FocusSupervisionEventType, timestampMs: Long) {
        val occurrenceCount = eventHistory.count { it.type == type } + 1
        eventHistory.add(
            FocusSupervisionEvent(
                type = type,
                startedAt = timestampMs,
                durationMs = 0L,
                confidence = null,
                occurrenceCount = occurrenceCount
            )
        )
    }

    fun getEvents(): List<FocusSupervisionEvent> = eventHistory.toList()

    fun reset() {
        eventHistory.clear()
        // Reset stats fields
        stats.readingDuration = 0
        stats.writingDuration = 0
        stats.typingDuration = 0
        stats.phoneUseCount = 0
        stats.phoneUseDuration = 0
        stats.penSpinningCount = 0
        stats.penSpinningDuration = 0
        stats.lookingAwayCount = 0
        stats.lookingAwayDuration = 0
        stats.drowsyCount = 0
        stats.drowsyDuration = 0
        stats.absentCount = 0
        stats.absentDuration = 0
    }
}
