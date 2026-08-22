package com.example.campusai.data.expression

import kotlin.math.ceil

/**
 * In-memory, anonymous performance counters for one expression-analysis session.
 * No image, face crop, label payload, or user identifier is retained here.
 */
data class ExpressionPerformanceSnapshot(
    val sessionDurationMs: Long,
    val processedFrames: Long,
    val droppedFrames: Long,
    val faceDetectionAverageMs: Double,
    val faceDetectionP50Ms: Double,
    val faceDetectionP95Ms: Double,
    val preprocessAverageMs: Double,
    val preprocessP50Ms: Double,
    val preprocessP95Ms: Double,
    val inferenceAverageMs: Double,
    val inferenceP50Ms: Double,
    val inferenceP95Ms: Double,
    val postprocessAverageMs: Double,
    val postprocessP50Ms: Double,
    val postprocessP95Ms: Double,
    val totalLatencyAverageMs: Double,
    val totalLatencyP50Ms: Double,
    val totalLatencyP95Ms: Double,
    val fps: Double,
    val noFaceRate: Double,
    val unknownRate: Double,
)

class ExpressionPerformanceStats {
    private val lock = Any()
    private var sessionStartedAtMs: Long? = null
    private val faceDetectionSamples = mutableListOf<Long>()
    private val preprocessSamples = mutableListOf<Long>()
    private val inferenceSamples = mutableListOf<Long>()
    private val postprocessSamples = mutableListOf<Long>()
    private val totalLatencySamples = mutableListOf<Long>()
    private var droppedFrames = 0L
    private var noFaceFrames = 0L
    private var unknownFrames = 0L

    fun start(startedAtMs: Long) = synchronized(lock) {
        if (sessionStartedAtMs == null) {
            sessionStartedAtMs = startedAtMs
        }
    }

    fun reset() = synchronized(lock) {
        sessionStartedAtMs = null
        faceDetectionSamples.clear()
        preprocessSamples.clear()
        inferenceSamples.clear()
        postprocessSamples.clear()
        totalLatencySamples.clear()
        droppedFrames = 0L
        noFaceFrames = 0L
        unknownFrames = 0L
    }

    fun recordFrame(
        faceDetectionMs: Long,
        preprocessMs: Long,
        inferenceMs: Long,
        postprocessMs: Long,
        totalLatencyMs: Long,
        noFace: Boolean,
        unknown: Boolean,
    ) = synchronized(lock) {
        faceDetectionSamples += faceDetectionMs.coerceAtLeast(0L)
        preprocessSamples += preprocessMs.coerceAtLeast(0L)
        inferenceSamples += inferenceMs.coerceAtLeast(0L)
        postprocessSamples += postprocessMs.coerceAtLeast(0L)
        totalLatencySamples += totalLatencyMs.coerceAtLeast(0L)
        if (noFace) noFaceFrames++
        if (unknown) unknownFrames++
    }

    fun recordDroppedFrame() = synchronized(lock) {
        droppedFrames++
    }

    fun snapshot(nowMs: Long): ExpressionPerformanceSnapshot = synchronized(lock) {
        val startedAt = sessionStartedAtMs ?: nowMs
        val durationMs = (nowMs - startedAt).coerceAtLeast(0L)
        val processed = totalLatencySamples.size.toLong()
        return ExpressionPerformanceSnapshot(
            sessionDurationMs = durationMs,
            processedFrames = processed,
            droppedFrames = droppedFrames,
            faceDetectionAverageMs = faceDetectionSamples.averageValue(),
            faceDetectionP50Ms = faceDetectionSamples.percentile(0.50),
            faceDetectionP95Ms = faceDetectionSamples.percentile(0.95),
            preprocessAverageMs = preprocessSamples.averageValue(),
            preprocessP50Ms = preprocessSamples.percentile(0.50),
            preprocessP95Ms = preprocessSamples.percentile(0.95),
            inferenceAverageMs = inferenceSamples.averageValue(),
            inferenceP50Ms = inferenceSamples.percentile(0.50),
            inferenceP95Ms = inferenceSamples.percentile(0.95),
            postprocessAverageMs = postprocessSamples.averageValue(),
            postprocessP50Ms = postprocessSamples.percentile(0.50),
            postprocessP95Ms = postprocessSamples.percentile(0.95),
            totalLatencyAverageMs = totalLatencySamples.averageValue(),
            totalLatencyP50Ms = totalLatencySamples.percentile(0.50),
            totalLatencyP95Ms = totalLatencySamples.percentile(0.95),
            fps = if (durationMs > 0L) processed * 1_000.0 / durationMs else 0.0,
            noFaceRate = if (processed > 0L) noFaceFrames.toDouble() / processed else 0.0,
            unknownRate = if (processed > 0L) unknownFrames.toDouble() / processed else 0.0,
        )
    }

    private fun List<Long>.averageValue(): Double =
        if (isEmpty()) 0.0 else average()

    private fun List<Long>.percentile(fraction: Double): Double {
        if (isEmpty()) return 0.0
        val sorted = sorted()
        val index = ceil((sorted.lastIndex * fraction).coerceIn(0.0, sorted.lastIndex.toDouble())).toInt()
        return sorted[index].toDouble()
    }
}
