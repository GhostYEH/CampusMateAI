package com.example.campusai.data.expression

import com.example.campusai.data.model.LearningStateLabel
import java.util.ArrayDeque

/** Aggregates raw independent-state logits from one continuously tracked face. */
class LearningStateWindow(
    private val requiredFrames: Int = 4,
    private val maxAgeMs: Long = 5_000L,
    private val scales: DoubleArray = doubleArrayOf(1.0, 1.0, 1.0),
    private val biases: DoubleArray = doubleArrayOf(0.0, 0.0, 0.0),
) {
    data class Snapshot(
        val probabilities: Map<LearningStateLabel, Double>,
        val frameCount: Int,
    )

    private data class Sample(val timestampMs: Long, val logits: FloatArray)

    private val samples = ArrayDeque<Sample>()
    private var trackingId: Int? = null
    private var lastTimestampMs: Long? = null

    init {
        require(requiredFrames > 0)
        require(maxAgeMs > 0L)
        require(scales.size == ExpressionMath.learningStateLabels.size)
        require(biases.size == ExpressionMath.learningStateLabels.size)
        require(scales.all { it.isFinite() && it >= 0.0 })
        require(biases.all { it.isFinite() })
    }

    @Synchronized
    fun add(logits: FloatArray, faceTrackingId: Int?, timestampMs: Long): Snapshot {
        if (faceTrackingId == null || logits.size != ExpressionMath.learningStateLabels.size ||
            logits.any { !it.isFinite() } || timestampMs < 0L
        ) {
            reset()
            return Snapshot(emptyMap(), 0)
        }
        val previousTimestamp = lastTimestampMs
        if (trackingId != faceTrackingId ||
            previousTimestamp != null && (timestampMs <= previousTimestamp || timestampMs - previousTimestamp > maxAgeMs)
        ) {
            clearSamples()
        }
        trackingId = faceTrackingId
        lastTimestampMs = timestampMs
        while (samples.isNotEmpty() && timestampMs - samples.first.timestampMs > maxAgeMs) {
            samples.removeFirst()
        }
        samples.addLast(Sample(timestampMs, logits.copyOf()))
        while (samples.size > requiredFrames) samples.removeFirst()
        if (samples.size < requiredFrames) return Snapshot(emptyMap(), samples.size)

        val meanLogits = DoubleArray(ExpressionMath.learningStateLabels.size)
        samples.forEach { sample ->
            sample.logits.forEachIndexed { index, value -> meanLogits[index] += value }
        }
        val probabilities = ExpressionMath.learningStateLabels.mapIndexed { index, label ->
            val mean = meanLogits[index] / requiredFrames
            label to ExpressionMath.sigmoid(mean * scales[index] + biases[index])
        }.toMap()
        return Snapshot(probabilities, samples.size)
    }

    @Synchronized
    fun reset() {
        clearSamples()
        trackingId = null
        lastTimestampMs = null
    }

    private fun clearSamples() {
        samples.clear()
    }
}
