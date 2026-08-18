package com.example.campusai.data.behavior

/** Presence is independent from the V3.2 study-behavior classification. */
enum class PresenceState {
    PRESENT,
    OBSERVING,
    ABSENT,
}

data class PresenceConfig(
    /** A recently detected person remains primary Presence evidence for this long. */
    val personHoldMs: Long = 2_000L,
    /** No person, face, or reliable visible-study evidence for this long confirms absence. */
    val presenceGraceMs: Long = 12_000L,
)

data class PresenceSnapshot(
    val state: PresenceState = PresenceState.OBSERVING,
    val lastPresenceEvidenceAtMs: Long? = null,
    val personDetected: Boolean = false,
    val recentPersonEvidence: Boolean = false,
    val faceDetected: Boolean = false,
    val behaviorEvidence: Boolean = false,
) {
    fun lastPresenceEvidenceAgoMs(nowMs: Long): Long? =
        lastPresenceEvidenceAtMs?.let { (nowMs - it).coerceAtLeast(0L) }
}

/**
 * Conservatively fuses independently-produced, current evidence. Either a face
 * or an already-stable V3.2 VISIBLE_STUDY result immediately restores PRESENT.
 */
class PresenceStateMachine(
    private val config: PresenceConfig = PresenceConfig(),
) {
    private var state = PresenceState.OBSERVING
    private var lastPresenceEvidenceAtMs: Long? = null
    private var lastPersonDetectedAtMs: Long? = null

    fun reset() {
        state = PresenceState.OBSERVING
        lastPresenceEvidenceAtMs = null
        lastPersonDetectedAtMs = null
    }

    fun process(
        timestampMs: Long,
        personDetected: Boolean,
        faceDetected: Boolean,
        behaviorEvidence: Boolean,
    ): PresenceSnapshot {
        if (personDetected) {
            lastPersonDetectedAtMs = timestampMs
        }
        val recentPersonEvidence = lastPersonDetectedAtMs?.let {
            timestampMs - it <= config.personHoldMs
        } ?: false
        if (recentPersonEvidence || faceDetected || behaviorEvidence) {
            lastPresenceEvidenceAtMs = timestampMs
            state = PresenceState.PRESENT
        } else {
            val lastEvidenceAt = lastPresenceEvidenceAtMs
            state = when {
                lastEvidenceAt == null -> PresenceState.OBSERVING
                timestampMs - lastEvidenceAt >= config.presenceGraceMs -> PresenceState.ABSENT
                // Once Presence has been confirmed, short total evidence loss is
                // deliberately retained as PRESENT. OBSERVING is initialization-only.
                else -> PresenceState.PRESENT
            }
        }
        return PresenceSnapshot(
            state = state,
            lastPresenceEvidenceAtMs = lastPresenceEvidenceAtMs,
            personDetected = personDetected,
            recentPersonEvidence = recentPersonEvidence,
            faceDetected = faceDetected,
            behaviorEvidence = behaviorEvidence,
        )
    }
}
