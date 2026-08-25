package com.example.campusai.data.behavior

enum class BehaviorProductLabel {
    STUDY_ACTIVITY,
    PHONE_INTERACTION,
    NO_VISIBLE_STUDY,
    UNCERTAIN,
}

data class BehaviorFramePrediction(
    val timestampMs: Long,
    val label: BehaviorProductLabel,
    val confidence: Float,
    val qualityAccepted: Boolean,
)

data class BehaviorEvent(
    val label: BehaviorProductLabel,
    val startedAtMs: Long,
    val endedAtMs: Long?,
    val confidence: Float,
    val active: Boolean,
    val reminderAllowed: Boolean,
)

class BehaviorEventAggregator(
    private val phoneEnterMs: Long = 2_000L,
    private val exitMs: Long = 1_000L,
    private val reminderCooldownMs: Long = 600_000L,
    private val minimumConfidence: Float = 0.5f,
) {
    private var candidateStartedAt: Long? = null
    private val candidateConfidences = mutableListOf<Float>()
    private var activeStartedAt: Long? = null
    private var exitStartedAt: Long? = null
    private var activeConfidence = 0f
    private var lastReminderAt: Long? = null

    fun update(frame: BehaviorFramePrediction): List<BehaviorEvent> {
        if (frame.timestampMs < 0L || !frame.qualityAccepted || frame.label == BehaviorProductLabel.UNCERTAIN) {
            return emptyList()
        }
        val phone = frame.label == BehaviorProductLabel.PHONE_INTERACTION && frame.confidence >= minimumConfidence
        if (phone) {
            exitStartedAt = null
            if (activeStartedAt != null) return emptyList()
            val start = candidateStartedAt
            if (start == null) {
                candidateStartedAt = frame.timestampMs
                candidateConfidences.clear()
                candidateConfidences += frame.confidence
                return emptyList()
            }
            candidateConfidences += frame.confidence
            if (frame.timestampMs - start < phoneEnterMs) return emptyList()
            activeStartedAt = start
            activeConfidence = candidateConfidences.average().toFloat()
            val reminderAllowed = lastReminderAt?.let {
                frame.timestampMs - it >= reminderCooldownMs
            } ?: true
            if (reminderAllowed) lastReminderAt = frame.timestampMs
            return listOf(
                BehaviorEvent(
                    label = BehaviorProductLabel.PHONE_INTERACTION,
                    startedAtMs = start,
                    endedAtMs = null,
                    confidence = activeConfidence,
                    active = true,
                    reminderAllowed = reminderAllowed,
                ),
            )
        }

        candidateStartedAt = null
        candidateConfidences.clear()
        val activeStart = activeStartedAt ?: run {
            exitStartedAt = null
            return emptyList()
        }
        val exitStart = exitStartedAt
        if (exitStart == null) {
            exitStartedAt = frame.timestampMs
            return emptyList()
        }
        if (frame.timestampMs - exitStart < exitMs) return emptyList()
        val event = BehaviorEvent(
            label = BehaviorProductLabel.PHONE_INTERACTION,
            startedAtMs = activeStart,
            endedAtMs = frame.timestampMs,
            confidence = activeConfidence,
            active = false,
            reminderAllowed = false,
        )
        activeStartedAt = null
        exitStartedAt = null
        activeConfidence = 0f
        return listOf(event)
    }

    fun reset() {
        candidateStartedAt = null
        candidateConfidences.clear()
        activeStartedAt = null
        exitStartedAt = null
        activeConfidence = 0f
        lastReminderAt = null
    }
}
