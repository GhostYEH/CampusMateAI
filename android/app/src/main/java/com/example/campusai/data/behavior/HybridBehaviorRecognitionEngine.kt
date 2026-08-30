package com.example.campusai.data.behavior

import android.graphics.Bitmap
import android.graphics.RectF

/** Runs V3.4 continuously and invokes TSM only when temporal confirmation is useful. */
class HybridBehaviorRecognitionEngine(
    private val singleFrameEngine: BehaviorRecognitionEngine,
    private val temporalEngine: BehaviorRecognitionEngine,
) : BehaviorRecognitionEngine {
    private val frameBuffer = ArrayDeque<Bitmap>()
    private var lastTemporalAtMs = 0L
    private var previousSingleTop: StudyBehavior? = null
    private var computerConfirmationCount = 0
    private var latestTemporalPrediction: BehaviorPrediction? = null

    override val isAvailable: Boolean get() = singleFrameEngine.isAvailable

    override fun initialize() {
        singleFrameEngine.initialize()
        temporalEngine.initialize()
    }

    override fun analyzeTemporalWindow(
        frames: List<Bitmap>,
        timestampMs: Long,
    ): BehaviorPrediction = analyzeTemporalWindow(frames, timestampMs, null)

    @Synchronized
    override fun analyzeTemporalWindow(
        frames: List<Bitmap>,
        timestampMs: Long,
        personBoundingBox: RectF?,
    ): BehaviorPrediction {
        val single = singleFrameEngine.analyzeTemporalWindow(frames, timestampMs, personBoundingBox)
        if (single.modelState != BehaviorV34Contract.MODEL_STATE) {
            clearTemporalEvidence()
            return single
        }
        if (single.probabilities.isEmpty()) return single
        retainLatestFrame(frames.lastOrNull())

        val singleTop = single.probabilities.maxByOrNull { it.value }?.key
        val shouldRun = BehaviorHybridPolicy.shouldRunTemporal(
            single = single,
            previousSingleTop = previousSingleTop,
            nowMs = timestampMs,
            lastTemporalAtMs = lastTemporalAtMs,
            bufferedFrameCount = frameBuffer.size,
        )
        previousSingleTop = singleTop
        val ranTemporal = shouldRun && temporalEngine.isAvailable
        if (ranTemporal) {
            lastTemporalAtMs = timestampMs
            val temporal = temporalEngine.analyzeTemporalWindow(
                sampleEightFrames(),
                timestampMs,
                personBoundingBox,
            )
            if (temporal.probabilities.isNotEmpty()) {
                latestTemporalPrediction = temporal
                val temporalTop = temporal.probabilities.maxByOrNull { it.value }?.key
                computerConfirmationCount = if (temporalTop == StudyBehavior.COMPUTER) {
                    computerConfirmationCount + 1
                } else {
                    0
                }
            }
        }
        val temporal = latestTemporalPrediction ?: return single
        val fused = BehaviorHybridPolicy.fuse(
            single = single.probabilities,
            temporal = temporal.probabilities,
            computerConfirmed = computerConfirmationCount >= REQUIRED_COMPUTER_CONFIRMATIONS,
        )
        return BehaviorPrediction(
            probabilities = fused.probabilities,
            timestampMs = timestampMs,
            modelState = BehaviorHybridPolicy.MODEL_STATE,
            stableBehavior = fused.acceptedBehavior,
            debugInferenceLatencyMs = sumLatencies(
                single.debugInferenceLatencyMs,
                if (ranTemporal) temporal.debugInferenceLatencyMs else 0L,
            ),
            debugPreprocessingLatencyMs = sumLatencies(
                single.debugPreprocessingLatencyMs,
                if (ranTemporal) temporal.debugPreprocessingLatencyMs else 0L,
            ),
        )
    }

    private fun retainLatestFrame(frame: Bitmap?) {
        if (frame == null || frame.isRecycled) return
        frameBuffer.addLast(frame.copy(frame.config ?: Bitmap.Config.ARGB_8888, false))
        while (frameBuffer.size > MAX_BUFFERED_FRAMES) frameBuffer.removeFirst().recycle()
    }

    private fun sampleEightFrames(): List<Bitmap> {
        val retained = frameBuffer.toList()
        val lastIndex = retained.lastIndex
        return List(BehaviorTsmContract.INPUT_FRAME_COUNT) { segment ->
            retained[(segment * lastIndex) / (BehaviorTsmContract.INPUT_FRAME_COUNT - 1)]
        }
    }

    private fun sumLatencies(first: Long, second: Long): Long =
        if (first >= 0L && second >= 0L) first + second else -1L

    @Synchronized
    override fun reset() {
        clearTemporalEvidence()
        temporalEngine.reset()
        singleFrameEngine.reset()
    }

    private fun clearTemporalEvidence() {
        frameBuffer.forEach { if (!it.isRecycled) it.recycle() }
        frameBuffer.clear()
        lastTemporalAtMs = 0L
        previousSingleTop = null
        computerConfirmationCount = 0
        latestTemporalPrediction = null
    }

    @Synchronized
    override fun close() {
        reset()
        temporalEngine.close()
        singleFrameEngine.close()
    }

    private companion object {
        const val MAX_BUFFERED_FRAMES = 8
        const val REQUIRED_COMPUTER_CONFIRMATIONS = 2
    }
}
