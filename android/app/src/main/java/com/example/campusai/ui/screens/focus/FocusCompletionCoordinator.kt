package com.example.campusai.ui.screens.focus

import com.example.campusai.data.model.FocusSessionSummary
import java.util.concurrent.atomic.AtomicBoolean

/** Owns the exactly-once boundary shared by timer expiry and explicit completion. */
class FocusCompletionCoordinator(
    private val finishObservation: suspend (actualFocusMinutes: Int) -> FocusSessionSummary,
    private val finishRemote: suspend (summary: FocusSessionSummary) -> Boolean,
) {
    private val inFlight = AtomicBoolean(false)
    private var completed = false
    private var pendingSummary: FocusSessionSummary? = null

    val isCompleted: Boolean get() = completed

    suspend fun complete(actualFocusMinutes: Int): FocusSessionSummary? {
        if (completed || !inFlight.compareAndSet(false, true)) return null
        return try {
            val summary = pendingSummary ?: finishObservation(actualFocusMinutes)
            if (finishRemote(summary)) {
                pendingSummary = null
                completed = true
                summary
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
