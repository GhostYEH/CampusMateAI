package com.example.campusai.data.behavior

data class BehaviorHybridDecision(
    val probabilities: Map<StudyBehavior, Float>,
    val acceptedBehavior: StudyBehavior,
)

/** Exact label order of the exported CampusMate TSM MobileNetV2 model. */
object BehaviorTsmContract {
    const val MODEL_STATE = "READY_BEHAVIOR_TSM_V4"
    const val INPUT_FRAME_COUNT = 8

    val outputBehaviors = arrayOf(
        StudyBehavior.READING,
        StudyBehavior.WRITING,
        StudyBehavior.PHONE_USE,
        StudyBehavior.COMPUTER,
        StudyBehavior.IDLE,
    )

    fun decode(logits: FloatArray): Map<StudyBehavior, Float> {
        require(logits.size == outputBehaviors.size) {
            "Expected ${outputBehaviors.size} TSM logits, got ${logits.size}"
        }
        val values = BehaviorModelMath.softmax(logits)
        return outputBehaviors.indices.associate { index -> outputBehaviors[index] to values[index] }
    }
}

/** Category-aware V3.4 + TSM fusion and the low-power temporal trigger policy. */
object BehaviorHybridPolicy {
    const val MODEL_STATE = "READY_BEHAVIOR_HYBRID_V4"
    private const val MIN_TEMPORAL_INTERVAL_MS = 2_000L
    private const val PERIODIC_TEMPORAL_INTERVAL_MS = 3_000L
    private const val LOW_CONFIDENCE = 0.45f
    private const val NARROW_MARGIN = 0.10f
    private const val MINIMUM_CONFIDENCE = 0.35f
    private const val MINIMUM_MARGIN = 0.05f

    fun shouldRunTemporal(
        single: BehaviorPrediction,
        previousSingleTop: StudyBehavior?,
        nowMs: Long,
        lastTemporalAtMs: Long,
        bufferedFrameCount: Int,
    ): Boolean {
        if (bufferedFrameCount < BehaviorTsmContract.INPUT_FRAME_COUNT) return false
        val elapsed = nowMs - lastTemporalAtMs
        if (elapsed < MIN_TEMPORAL_INTERVAL_MS) return false
        val ranked = single.probabilities.entries.sortedByDescending { it.value }
        if (ranked.isEmpty()) return false
        val top = ranked[0]
        val margin = top.value - (ranked.getOrNull(1)?.value ?: 0f)
        val changed = previousSingleTop != null && previousSingleTop != top.key
        return elapsed >= PERIODIC_TEMPORAL_INTERVAL_MS ||
            top.value < LOW_CONFIDENCE ||
            margin < NARROW_MARGIN ||
            changed ||
            top.key == StudyBehavior.PHONE_USE
    }

    fun fuse(
        single: Map<StudyBehavior, Float>,
        temporal: Map<StudyBehavior, Float>,
        computerConfirmed: Boolean,
    ): BehaviorHybridDecision {
        val raw = linkedMapOf(
            StudyBehavior.READING to weighted(single, temporal, StudyBehavior.READING, 0.65f, 0.35f),
            StudyBehavior.WRITING to weighted(single, temporal, StudyBehavior.WRITING, 0.90f, 0.10f),
            StudyBehavior.PHONE_USE to weighted(single, temporal, StudyBehavior.PHONE_USE, 0.45f, 0.55f),
            StudyBehavior.COMPUTER to if (computerConfirmed) temporal[StudyBehavior.COMPUTER].orZero() else 0f,
            StudyBehavior.IDLE to weighted(single, temporal, StudyBehavior.IDLE, 0.55f, 0.45f),
        )
        val total = raw.values.sum()
        val probabilities = if (total > 0f) raw.mapValues { it.value / total } else raw
        val singleTop = single.maxByOrNull { it.value }?.key
        val ranked = probabilities.entries
            .filter { it.key != StudyBehavior.WRITING || singleTop == StudyBehavior.WRITING }
            .sortedByDescending { it.value }
        val top = ranked.firstOrNull()
        val margin = (top?.value ?: 0f) - (ranked.getOrNull(1)?.value ?: 0f)
        val accepted = if (
            top != null && top.value >= MINIMUM_CONFIDENCE && margin >= MINIMUM_MARGIN
        ) top.key else StudyBehavior.UNCERTAIN
        return BehaviorHybridDecision(probabilities, accepted)
    }

    private fun weighted(
        single: Map<StudyBehavior, Float>,
        temporal: Map<StudyBehavior, Float>,
        behavior: StudyBehavior,
        singleWeight: Float,
        temporalWeight: Float,
    ) = single[behavior].orZero() * singleWeight + temporal[behavior].orZero() * temporalWeight

    private fun Float?.orZero() = this ?: 0f
}
