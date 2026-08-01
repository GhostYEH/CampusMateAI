package com.example.campusai.data.focus

import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusSessionSummary
import kotlin.math.abs

/** All learning-assistance timing thresholds live here, rather than in UI code. */
data class FocusObservationConfig(
    val noFaceWindowMs: Long = 8_000,
    val headTurnWindowMs: Long = 4_000,
    val lowEyeOpenWindowMs: Long = 2_000,
    val reminderCooldownMs: Long = 3 * 60 * 1_000,
    val headTurnDegrees: Double = 22.0,
    val lowEyeOpenProbability: Double = 0.28,
)

enum class FocusState {
    FOCUSED,
    POSSIBLY_DISTRACTED,
    BREAK_SUGGESTED,
    NO_FACE,
    UNAVAILABLE,
}

data class FocusObservation(
    val timestamp: Long,
    val facePresent: Boolean,
    val headEulerAngleX: Double? = null,
    val headEulerAngleY: Double? = null,
    val headEulerAngleZ: Double? = null,
    val leftEyeOpenProbability: Double? = null,
    val rightEyeOpenProbability: Double? = null,
    val expression: ExpressionResult? = null,
    val inferenceAvailable: Boolean = true,
)

sealed interface FocusEvent {
    data object NoFaceRecorded : FocusEvent
    data object PossibleDistractionStarted : FocusEvent
    data class PossibleDistractionEnded(val durationMs: Long) : FocusEvent
    data object BreakSuggested : FocusEvent
}

data class FocusProcessingResult(
    val state: FocusState,
    val events: List<FocusEvent>,
)

/**
 * Converts coarse, on-device face signals into time-windowed auxiliary observations.
 * It intentionally never infers a diagnosis or a psychological state.
 */
class FocusStateProcessor(
    private val config: FocusObservationConfig = FocusObservationConfig(),
) {
    private var noFaceSince: Long? = null
    private var noFaceRecorded = false
    private var headTurnSince: Long? = null
    private var headTurnRecorded = false
    private var lowEyesSince: Long? = null
    private var lastSuggestionAt = Long.MIN_VALUE
    private var noFaceEvents = 0
    private var distractionDurationMs = 0L
    private var breakSuggestions = 0
    private val stableExpressions = linkedMapOf<String, Int>()

    fun process(observation: FocusObservation): FocusProcessingResult {
        val events = mutableListOf<FocusEvent>()
        recordStableExpression(observation.expression)
        if (!observation.inferenceAvailable) {
            closeHeadTurn(observation.timestamp, events)
            resetFaceWindows()
            return FocusProcessingResult(FocusState.UNAVAILABLE, events)
        }
        if (!observation.facePresent) {
            closeHeadTurn(observation.timestamp, events)
            lowEyesSince = null
            val since = noFaceSince ?: observation.timestamp.also { noFaceSince = it }
            if (!noFaceRecorded && observation.timestamp - since >= config.noFaceWindowMs) {
                noFaceRecorded = true
                noFaceEvents++
                events += FocusEvent.NoFaceRecorded
            }
            return FocusProcessingResult(if (noFaceRecorded) FocusState.NO_FACE else FocusState.FOCUSED, events)
        }

        noFaceSince = null
        noFaceRecorded = false
        val headTurned = listOfNotNull(observation.headEulerAngleY, observation.headEulerAngleZ)
            .any { abs(it) >= config.headTurnDegrees }
        val headState = updateHeadTurn(headTurned, observation.timestamp, events)
        val eyesLow = listOfNotNull(
            observation.leftEyeOpenProbability,
            observation.rightEyeOpenProbability,
        ).let { values -> values.size == 2 && values.all { it <= config.lowEyeOpenProbability } }
        val breakSuggested = updateLowEyes(eyesLow, observation.timestamp, events)
        return FocusProcessingResult(
            when {
                breakSuggested -> FocusState.BREAK_SUGGESTED
                headState -> FocusState.POSSIBLY_DISTRACTED
                else -> FocusState.FOCUSED
            },
            events,
        )
    }

    fun finish(now: Long, actualFocusMinutes: Int, modelVersion: String): FocusSessionSummary {
        closeHeadTurn(now, mutableListOf())
        return FocusSessionSummary(
            actualFocusMinutes = actualFocusMinutes.coerceAtLeast(0),
            noFaceEventCount = noFaceEvents,
            possibleDistractionDurationSeconds = distractionDurationMs / 1_000,
            breakSuggestionCount = breakSuggestions,
            stableExpressionDistribution = stableExpressions.toMap(),
            modelVersion = modelVersion,
        )
    }

    private fun updateHeadTurn(headTurned: Boolean, now: Long, events: MutableList<FocusEvent>): Boolean {
        if (!headTurned) {
            closeHeadTurn(now, events)
            return false
        }
        val since = headTurnSince ?: now.also { headTurnSince = it }
        if (!headTurnRecorded && now - since >= config.headTurnWindowMs) {
            headTurnRecorded = true
            events += FocusEvent.PossibleDistractionStarted
        }
        return headTurnRecorded
    }

    private fun closeHeadTurn(now: Long, events: MutableList<FocusEvent>) {
        if (headTurnRecorded) {
            val duration = (now - (headTurnSince ?: now)).coerceAtLeast(0)
            distractionDurationMs += duration
            events += FocusEvent.PossibleDistractionEnded(duration)
        }
        headTurnSince = null
        headTurnRecorded = false
    }

    private fun updateLowEyes(eyesLow: Boolean, now: Long, events: MutableList<FocusEvent>): Boolean {
        if (!eyesLow) {
            lowEyesSince = null
            return false
        }
        val since = lowEyesSince ?: now.also { lowEyesSince = it }
        if (
            now - since < config.lowEyeOpenWindowMs ||
            (lastSuggestionAt != Long.MIN_VALUE && now - lastSuggestionAt < config.reminderCooldownMs)
        ) {
            return false
        }
        lastSuggestionAt = now
        breakSuggestions++
        events += FocusEvent.BreakSuggested
        return true
    }

    private fun recordStableExpression(result: ExpressionResult?) {
        if (result?.isStable == true && result.label !in setOf(ExpressionLabel.UNKNOWN, ExpressionLabel.NO_FACE)) {
            stableExpressions[result.label.name] = (stableExpressions[result.label.name] ?: 0) + 1
        }
    }

    private fun resetFaceWindows() {
        noFaceSince = null
        noFaceRecorded = false
        lowEyesSince = null
    }
}
