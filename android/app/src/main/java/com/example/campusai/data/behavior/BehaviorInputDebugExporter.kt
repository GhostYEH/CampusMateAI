package com.example.campusai.data.behavior

import android.content.Context
import android.graphics.Bitmap
import android.os.Environment
import com.example.campusai.BuildConfig
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.util.concurrent.Executors
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
}

data class BehaviorDatasetCaptureState(
    val active: Boolean = false,
    val label: BehaviorDatasetLabel? = null,
    val sessionId: String? = null,
    val capturedCount: Int = 0,
)

/**
 * Debug-only capture of the exact bitmaps passed to behavior preprocessing.
 * Release builds return before allocating or writing any image data.
 */
object BehaviorInputDebugExporter {
    private const val EXPORT_INTERVAL_MS = 2_000L
    private const val MAX_SAVED_IMAGES = 24
    private const val DATASET_CAPTURE_INTERVAL_MS = 1_000L
    private const val MAX_DATASET_IMAGES_PER_SESSION = 180
    private val ioExecutor = Executors.newSingleThreadExecutor()
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
            val session = DatasetSession(label, sessionId, directory)
            activeDatasetSession = session
            _datasetCaptureState.value = BehaviorDatasetCaptureState(
                active = true,
                label = label,
                sessionId = sessionId,
            )
        }
    }

    fun stopDatasetSession() {
        if (!BuildConfig.DEBUG) return
        synchronized(datasetLock) {
            val session = activeDatasetSession ?: return
            activeDatasetSession = null
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
            stabilizedBehavior(displayState),
            uiBehaviorState(displayState),
        )
        OutputStreamWriter(FileOutputStream(file, true), Charsets.UTF_8).use { writer ->
            if (file.length() == 0L) {
                writer.appendLine(
                    "timestamp,image_filename,raw_idle_probability,raw_visible_study_probability," +
                        "raw_top1_class,raw_top1_confidence," +
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

    private fun appendDatasetMetadata(session: DatasetSession, timestampMs: Long, filename: String) {
        val file = File(session.directory, "session_metadata.csv")
        OutputStreamWriter(FileOutputStream(file, true), Charsets.UTF_8).use { writer ->
            if (file.length() == 0L) {
                writer.appendLine("label,session_id,timestamp,image_filename")
            }
            writer.appendLine(
                listOf(session.label.directoryName, session.id, timestampMs.toString(), filename)
                    .joinToString(",") { csvValue(it) },
            )
        }
    }

    private val UI_BEHAVIORS = setOf(
        StudyBehavior.IDLE,
        StudyBehavior.VISIBLE_STUDY,
    )

    private class DatasetSession(
        val label: BehaviorDatasetLabel,
        val id: String,
        val directory: File,
        var lastCaptureAt: Long = Long.MIN_VALUE,
        var reservedCount: Int = 0,
    )
}
