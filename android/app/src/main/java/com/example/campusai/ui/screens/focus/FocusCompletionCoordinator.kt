package com.example.campusai.ui.screens.focus

import com.example.campusai.data.model.FocusSessionSummary
import java.util.concurrent.atomic.AtomicBoolean

data class FocusCompletionResult(
    val summary: FocusSessionSummary,
    val completePlanStep: Boolean,
)

/** Owns the exactly-once boundary shared by timer expiry and explicit completion. */
class FocusCompletionCoordinator(
    private val finishObservation: suspend (actualFocusMinutes: Int) -> FocusSessionSummary,
    private val finishRemote: suspend (summary: FocusSessionSummary, selfReport: String?) -> Boolean,
) {
    private val inFlight = AtomicBoolean(false)
    private var completed = false
    private var pendingSummary: FocusSessionSummary? = null

    val isCompleted: Boolean get() = completed

    suspend fun complete(
        actualFocusMinutes: Int,
        selfReport: String? = null,
        completePlanStep: Boolean = false,
    ): FocusCompletionResult? {
        if (completed || !inFlight.compareAndSet(false, true)) return null
        return try {
            val summary = pendingSummary ?: finishObservation(actualFocusMinutes)
            if (finishRemote(summary, selfReport?.trim()?.takeIf { it.isNotEmpty() })) {
                pendingSummary = null
                completed = true
                FocusCompletionResult(summary, completePlanStep)
            } else {
                pendingSummary = summary
                null
            }
        } finally {
            inFlight.set(false)
        }
    }
}

internal fun presentFocusReminder(
    sessionMode: com.example.campusai.data.model.FocusSessionMode,
    observationEnabled: Boolean,
    reminder: String?,
): String? = reminder
    ?.trim()
    ?.takeIf {
        it.isNotEmpty() && observationEnabled &&
            sessionMode == com.example.campusai.data.model.FocusSessionMode.SMART_GUARD
    }
