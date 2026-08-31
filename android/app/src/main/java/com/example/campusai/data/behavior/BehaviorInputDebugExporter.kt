package com.example.campusai.data.behavior

import android.content.Context
import android.graphics.Bitmap
import android.os.Environment
import com.example.campusai.BuildConfig
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class BehaviorDatasetLabel(
    val directoryName: String,
    val displayName: String,
) {
    IDLE("idle", "暂无明确学习"),
    VISIBLE_STUDY("visible_study", "可见学习行为"),
    /** Kept for reading and extending historical V3.1 collection sessions. */
    ACTIVE_STUDY("active_study", "学习行为（历史）"),
    // Debug-only V3.2 benchmark samples that are visibly studying but visually difficult.
    VISIBLE_STUDY_HARD("visible_study_hard", "可见学习 Hard Case"),
}

data class BehaviorDatasetCaptureState(
    val active: Boolean = false,
    val preparing: Boolean = false,
    val preparationSecondsRemaining: Int = 0,
    val label: BehaviorDatasetLabel? = null,
    val sessionId: String? = null,
    val capturedCount: Int = 0,
)

val BehaviorDatasetCaptureState.isRunning: Boolean
    get() = active || preparing
/**
 * Debug-only capture of the exact bitmaps passed to behavior preprocessing.
 * Release builds return before allocating or writing any image data.
 */
object BehaviorInputDebugExporter {
    private const val EXPORT_INTERVAL_MS = 2_000L
    private const val MAX_SAVED_IMAGES = 24
    private const val DATASET_CAPTURE_INTERVAL_MS = 1_000L
    private const val MAX_DATASET_IMAGES_PER_SESSION = 120
    private const val DATASET_CAPTURE_PREPARATION_MS = 5_000L
    private val ioExecutor = Executors.newSingleThreadExecutor()
    private val countdownExecutor = Executors.newSingleThreadScheduledExecutor()
    private const val MAX_PENDING_PREDICTIONS = MAX_SAVED_IMAGES
    private const val MAX_PREDICTION_CSV_BYTES = 512 * 1_024L
    private const val MAX_DATASET_SESSIONS_PER_LABEL = 8
    private val lastExportAt = AtomicLong(Long.MIN_VALUE)
    private val capturedImageFilenames = ConcurrentHashMap<Long, String>()
    private val sessionPrepared = AtomicBoolean(false)
    private val datasetLock = Any()
    private var activeDatasetSession: DatasetSession? = null
    private val _datasetCaptureState = MutableStateFlow(BehaviorDatasetCaptureState())
    val datasetCaptureState: StateFlow<BehaviorDatasetCaptureState> = _datasetCaptureState.asStateFlow()

    fun export(
        context: Context,
        behaviorInput: Bitmap,
        resizedRgbInput: Bitmap,
        timestampMs: Long,
    ) {
        if (!BuildConfig.DEBUG) return

        if (claimExportSlot(timestampMs)) {
            exportDebugImages(context, behaviorInput, resizedRgbInput, timestampMs)
        }
        captureDatasetImage(context, behaviorInput, timestampMs)
    }

    private fun exportDebugImages(
        context: Context,
        behaviorInput: Bitmap,
        resizedRgbInput: Bitmap,
        timestampMs: Long,
    ) {
        val behaviorInputCopy = behaviorInput.copy(
            behaviorInput.config ?: Bitmap.Config.ARGB_8888,
            false,
        )
        val resizedRgbCopy = resizedRgbInput.copy(
            resizedRgbInput.config ?: Bitmap.Config.ARGB_8888,
            false,
        )
        val behaviorInputFilename =
            "${timestampMs}_behavior_input_${behaviorInputCopy.width}x${behaviorInputCopy.height}.png"
        capturedImageFilenames[timestampMs] = behaviorInputFilename
        val pendingOverflow = capturedImageFilenames.size - MAX_PENDING_PREDICTIONS
        if (pendingOverflow > 0) {
            capturedImageFilenames.keys
                .sorted()
                .take(pendingOverflow)
                .forEach(capturedImageFilenames::remove)
        }
        ioExecutor.execute {
            try {
                val directory = debugDirectory(context)
                if (!directory.exists() && !directory.mkdirs()) return@execute
                prepareSession(directory)

                savePng(
                    behaviorInputCopy,
                    File(directory, behaviorInputFilename),
                )
                savePng(
                    resizedRgbCopy,
                    File(directory, "${timestampMs}_onnx_rgb_${resizedRgbCopy.width}x${resizedRgbCopy.height}.png"),
                )
                val savedFiles = directory.listFiles()
                    ?.sortedBy { it.lastModified() }
                    .orEmpty()
                savedFiles
                    .take((savedFiles.size - MAX_SAVED_IMAGES).coerceAtLeast(0))
                    .forEach { it.delete() }
            } finally {
                behaviorInputCopy.recycle()
                resizedRgbCopy.recycle()
            }
        }
    }

    fun startDatasetSession(context: Context, label: BehaviorDatasetLabel) {
        if (!BuildConfig.DEBUG) return
        synchronized(datasetLock) {
            if (activeDatasetSession != null) return
            val labelDirectory = File(datasetRootDirectory(context), label.directoryName)
            if (!labelDirectory.exists() && !labelDirectory.mkdirs()) return
            val sessionId = nextSessionId(labelDirectory)
            val directory = File(labelDirectory, sessionId)
            if (!directory.mkdirs()) return
            val sessionStartedAtMs = System.currentTimeMillis()
            val session = DatasetSession(
                label = label,
                id = sessionId,
                directory = directory,
                sessionStartedAtMs = sessionStartedAtMs,
                captureStartedAtMs = sessionStartedAtMs + DATASET_CAPTURE_PREPARATION_MS,
            )
            activeDatasetSession = session
            _datasetCaptureState.value = BehaviorDatasetCaptureState(
                preparing = true,
                preparationSecondsRemaining = secondsRemaining(session.captureStartedAtMs, sessionStartedAtMs),
                label = label,
                sessionId = sessionId,
            )
            schedulePreparationUpdates(session)
            pruneDatasetSessions(labelDirectory, keep = directory)
        }
    }

    fun stopDatasetSession() {
        if (!BuildConfig.DEBUG) return
        synchronized(datasetLock) {
            val session = activeDatasetSession ?: return
            activeDatasetSession = null
            session.preparationTask?.cancel(false)
            _datasetCaptureState.value = BehaviorDatasetCaptureState(
                label = session.label,
                sessionId = session.id,
                capturedCount = session.reservedCount,
            )
        }
    }

    private fun captureDatasetImage(context: Context, behaviorInput: Bitmap, timestampMs: Long) {
        val session = synchronized(datasetLock) {
            val current = activeDatasetSession ?: return
            if (timestampMs < current.captureStartedAtMs) return
            markCaptureStartedLocked(current, timestampMs)
            if (
                current.reservedCount >= MAX_DATASET_IMAGES_PER_SESSION ||
                (current.lastCaptureAt != Long.MIN_VALUE &&
                    timestampMs - current.lastCaptureAt < DATASET_CAPTURE_INTERVAL_MS)
            ) {
                return
            }
            current.lastCaptureAt = timestampMs
            current.reservedCount += 1
            _datasetCaptureState.value = BehaviorDatasetCaptureState(
                active = true,
                label = current.label,
                sessionId = current.id,
                capturedCount = current.reservedCount,
            )
            current
        }
        val copy = behaviorInput.copy(behaviorInput.config ?: Bitmap.Config.ARGB_8888, false)
        ioExecutor.execute {
            try {
                synchronized(datasetLock) {
                    if (activeDatasetSession !== session) return@execute
                }
                val filename = "${timestampMs}_behavior_input_${copy.width}x${copy.height}.png"
                savePng(copy, File(session.directory, filename))
                appendDatasetMetadata(session, timestampMs, filename)
                synchronized(datasetLock) {
                    if (
                        activeDatasetSession === session &&
                        session.reservedCount >= MAX_DATASET_IMAGES_PER_SESSION
                    ) {
                        activeDatasetSession = null
                        _datasetCaptureState.value = BehaviorDatasetCaptureState(
                            label = session.label,
                            sessionId = session.id,
                            capturedCount = session.reservedCount,
                        )
                    }
                }
            } finally {
                copy.recycle()
            }
        }
    }

    /** Records the raw and stabilized state only for a timestamp whose images were exported. */
    fun recordPrediction(
        context: Context,
        prediction: BehaviorPrediction,
        displayState: BehaviorDisplayState,
    ) {
        if (!BuildConfig.DEBUG) return
        val imageFilename = capturedImageFilenames.remove(prediction.timestampMs) ?: return
        ioExecutor.execute {
            val directory = debugDirectory(context)
            if (!directory.exists() && !directory.mkdirs()) return@execute
            prepareSession(directory)
            appendPredictionCsv(
                file = File(directory, "behavior_debug_predictions.csv"),
                prediction = prediction,
                imageFilename = imageFilename,
                displayState = displayState,
            )
        }
    }

    private fun claimExportSlot(timestampMs: Long): Boolean {
        while (true) {
            val previous = lastExportAt.get()
            if (previous != Long.MIN_VALUE && timestampMs - previous < EXPORT_INTERVAL_MS) return false
            if (lastExportAt.compareAndSet(previous, timestampMs)) return true
        }
    }

    private fun savePng(bitmap: Bitmap, file: File) {
        FileOutputStream(file).use { output ->
            check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) {
                "Could not save behavior debug image"
            }
        }
    }

    private fun debugDirectory(context: Context) = File(
        context.getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: context.cacheDir,
        "behavior_debug",
    )

    private fun datasetRootDirectory(context: Context) = File(
        context.getExternalFilesDir(Environment.DIRECTORY_PICTURES) ?: context.cacheDir,
        "behavior_dataset",
    )

    private fun prepareSession(directory: File) {
        if (sessionPrepared.compareAndSet(false, true)) {
            File(directory, "behavior_debug_predictions.csv").delete()
        }
    }

    private fun appendPredictionCsv(
        file: File,
        prediction: BehaviorPrediction,
        imageFilename: String,
        displayState: BehaviorDisplayState,
    ) {
        if (file.length() >= MAX_PREDICTION_CSV_BYTES) {
            file.delete()
        }
        val probabilities = prediction.probabilities
        val top = probabilities
            .filterKeys { it in UI_BEHAVIORS }
            .maxByOrNull { it.value }
        val values = listOf(
            prediction.timestampMs.toString(),
            imageFilename,
            (probabilities[StudyBehavior.IDLE] ?: 0f).toString(),
            (probabilities[StudyBehavior.VISIBLE_STUDY] ?: 0f).toString(),
            top?.key?.name.orEmpty(),
            (top?.value ?: 0f).toString(),
            prediction.debugPreprocessingLatencyMs.toString(),
            prediction.debugInferenceLatencyMs.toString(),
            stabilizedBehavior(displayState),
            uiBehaviorState(displayState),
        )
        OutputStreamWriter(FileOutputStream(file, true), Charsets.UTF_8).use { writer ->
            if (file.length() == 0L) {
                writer.appendLine(
                    "timestamp,image_filename,raw_idle_probability,raw_visible_study_probability," +
                        "raw_top1_class,raw_top1_confidence," +
                        "preprocessing_latency_ms,inference_latency_ms," +
                        "stabilized_behavior,ui_behavior_state",
                )
            }
            writer.appendLine(values.joinToString(",") { csvValue(it) })
        }
    }

    private fun stabilizedBehavior(displayState: BehaviorDisplayState): String = when (displayState) {
        is BehaviorDisplayState.Stable -> displayState.behavior.name
        else -> "NONE"
    }

    private fun uiBehaviorState(displayState: BehaviorDisplayState): String = when (displayState) {
        BehaviorDisplayState.Observing -> "正在观察..."
        BehaviorDisplayState.NoStableBehavior -> "暂未识别出稳定行为"
        is BehaviorDisplayState.Stable -> {
            val label = when (displayState.behavior) {
                StudyBehavior.VISIBLE_STUDY -> "检测到学习行为"
                StudyBehavior.READING -> "检测到阅读"
                StudyBehavior.WRITING -> "检测到书写"
                StudyBehavior.COMPUTER -> "检测到电脑学习"
                StudyBehavior.PHONE_USE -> "检测到手机交互"
                StudyBehavior.IDLE -> "暂未检测到明确学习行为"
                else -> "正在观察"
            }
            "$label ${(displayState.confidence * 100).toInt()}%"
        }
    }

    private fun csvValue(value: String): String = "\"${value.replace("\"", "\"\"")}\""

    private fun nextSessionId(labelDirectory: File): String {
        val next = labelDirectory.listFiles()
            .orEmpty()
            .mapNotNull { file -> Regex("session_(\\d+)").matchEntire(file.name)?.groupValues?.get(1)?.toIntOrNull() }
            .maxOrNull()
            ?.plus(1)
            ?: 1
        return "session_%03d".format(next)
    }

    private fun pruneDatasetSessions(labelDirectory: File, keep: File) {
        val sessions = labelDirectory.listFiles()
            .orEmpty()
            .filter { it.isDirectory && it.name.startsWith("session_") }
            .sortedBy { it.lastModified() }
        val overflow = sessions.size - MAX_DATASET_SESSIONS_PER_LABEL
        if (overflow <= 0) return
        sessions
            .filter { it != keep }
            .take(overflow)
            .forEach { it.deleteRecursively() }
    }
    private fun appendDatasetMetadata(session: DatasetSession, timestampMs: Long, filename: String) {
        val file = File(session.directory, "session_metadata.csv")
        OutputStreamWriter(FileOutputStream(file, true), Charsets.UTF_8).use { writer ->
            if (file.length() == 0L) {
                writer.appendLine(
                    "label,session_id,session_started_at,capture_started_at,capture_delay_ms,timestamp,image_filename",
                )
            }
            writer.appendLine(
                listOf(
                    session.label.directoryName,
                    session.id,
                    session.sessionStartedAtMs.toString(),
                    session.captureStartedAtMs.toString(),
                    DATASET_CAPTURE_PREPARATION_MS.toString(),
                    timestampMs.toString(),
                    filename,
                )
                    .joinToString(",") { csvValue(it) },
            )
        }
    }

    private fun schedulePreparationUpdates(session: DatasetSession) {
        session.preparationTask = countdownExecutor.scheduleAtFixedRate({
            synchronized(datasetLock) {
                if (activeDatasetSession !== session) {
                    session.preparationTask?.cancel(false)
                    return@scheduleAtFixedRate
                }
                markCaptureStartedLocked(session, System.currentTimeMillis())
            }
        }, 200L, 200L, java.util.concurrent.TimeUnit.MILLISECONDS)
    }

    private fun markCaptureStartedLocked(session: DatasetSession, nowMs: Long) {
        if (nowMs < session.captureStartedAtMs) {
            _datasetCaptureState.value = BehaviorDatasetCaptureState(
                preparing = true,
                preparationSecondsRemaining = secondsRemaining(session.captureStartedAtMs, nowMs),
                label = session.label,
                sessionId = session.id,
                capturedCount = session.reservedCount,
            )
            return
        }
        session.preparationTask?.cancel(false)
        _datasetCaptureState.value = BehaviorDatasetCaptureState(
            active = true,
            label = session.label,
            sessionId = session.id,
            capturedCount = session.reservedCount,
        )
    }

    private fun secondsRemaining(captureStartedAtMs: Long, nowMs: Long): Int =
        ((captureStartedAtMs - nowMs + 999L) / 1_000L).coerceAtLeast(0L).toInt()
    private val UI_BEHAVIORS = setOf(
        StudyBehavior.IDLE,
        StudyBehavior.VISIBLE_STUDY,
        StudyBehavior.READING,
        StudyBehavior.WRITING,
        StudyBehavior.COMPUTER,
        StudyBehavior.PHONE_USE,
    )

    private class DatasetSession(
        val label: BehaviorDatasetLabel,
        val id: String,
        val directory: File,
        val sessionStartedAtMs: Long,
        val captureStartedAtMs: Long,
        var lastCaptureAt: Long = Long.MIN_VALUE,
        var reservedCount: Int = 0,
        var preparationTask: ScheduledFuture<*>? = null,
    )
}
