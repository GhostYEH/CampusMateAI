package com.example.campusai.data.classroom.focus

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import com.example.campusai.BuildConfig
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class ClassroomObservationExportFormat(
    val extension: String,
    val mimeType: String,
) {
    CSV("csv", "text/csv"),
    JSON("json", "application/json"),
}

/**
 * 窗口级复盘导出。内容严格限定为会话内相对时间、数值统计、事件计数和不可观察
 * 原因；不包含课堂标题、账号、设备标识、原始帧或人脸特征。
 */
object ClassroomObservationExport {
    fun encode(
        format: ClassroomObservationExportFormat,
        windows: List<ClassroomObservationWindow>,
    ): String = when (format) {
        ClassroomObservationExportFormat.CSV -> csv(windows)
        ClassroomObservationExportFormat.JSON -> json(windows)
    }

    fun csv(windows: List<ClassroomObservationWindow>): String {
        val header = listOf(
            "window_index",
            "start_offset_ms",
            "end_offset_ms",
            "complete",
            "valid_samples",
            "invalid_samples",
            "face_visible_samples",
            "face_visible_ratio",
            "yaw_mean_deg",
            "yaw_std_deg",
            "yaw_min_deg",
            "yaw_max_deg",
            "yaw_samples",
            "pitch_mean_deg",
            "pitch_std_deg",
            "pitch_min_deg",
            "pitch_max_deg",
            "pitch_samples",
            "dominant_stage",
            "stage_counts",
            "manual_page_turns",
            "quiz_submissions",
            "questions",
            "verdict",
            "unavailable_reason",
            "unavailable_reason_counts",
        ).joinToString(",")
        val body = windows.joinToString("\n") { window ->
            listOf(
                window.index.toString(),
                window.startOffsetMs.toString(),
                window.endOffsetMs.toString(),
                window.complete.toString(),
                window.validSampleCount.toString(),
                window.invalidSampleCount.toString(),
                window.faceVisibleSampleCount.toString(),
                decimal(window.faceVisibleRatio),
                decimal(window.yaw?.mean),
                decimal(window.yaw?.standardDeviation),
                decimal(window.yaw?.min),
                decimal(window.yaw?.max),
                window.yaw?.samples?.toString().orEmpty(),
                decimal(window.pitch?.mean),
                decimal(window.pitch?.standardDeviation),
                decimal(window.pitch?.min),
                decimal(window.pitch?.max),
                window.pitch?.samples?.toString().orEmpty(),
                csvEscape(window.dominantStage.orEmpty()),
                csvEscape(window.stageCounts.entries.joinToString(";") { "${it.key}:${it.value}" }),
                window.manualPageTurns.toString(),
                window.quizSubmissions.toString(),
                window.questions.toString(),
                window.verdict.code,
                window.unavailableReason?.code.orEmpty(),
                csvEscape(
                    window.reasonCounts.entries.joinToString(";") { "${it.key.code}:${it.value}" },
                ),
            ).joinToString(",")
        }
        return header + "\n" + body + "\n"
    }

    fun json(windows: List<ClassroomObservationWindow>): String = buildString {
        append("{\"version\":1,\"windows\":[")
        windows.forEachIndexed { index, window ->
            if (index > 0) append(',')
            append('{')
            append("\"index\":").append(window.index).append(',')
            append("\"startOffsetMs\":").append(window.startOffsetMs).append(',')
            append("\"endOffsetMs\":").append(window.endOffsetMs).append(',')
            append("\"complete\":").append(window.complete).append(',')
            append("\"validSampleCount\":").append(window.validSampleCount).append(',')
            append("\"invalidSampleCount\":").append(window.invalidSampleCount).append(',')
            append("\"faceVisibleSampleCount\":").append(window.faceVisibleSampleCount).append(',')
            append("\"faceVisibleRatio\":").append(decimal(window.faceVisibleRatio)).append(',')
            append("\"yaw\":").append(jsonAxis(window.yaw)).append(',')
            append("\"pitch\":").append(jsonAxis(window.pitch)).append(',')
            append("\"stageCounts\":").append(jsonCounts(window.stageCounts)).append(',')
            append("\"dominantStage\":")
                .append(window.dominantStage?.let { "\"${jsonEscape(it)}\"" } ?: "null").append(',')
            append("\"manualPageTurns\":").append(window.manualPageTurns).append(',')
            append("\"quizSubmissions\":").append(window.quizSubmissions).append(',')
            append("\"questions\":").append(window.questions).append(',')
            append("\"verdict\":\"${window.verdict.code}\",")
            append("\"unavailableReason\":")
                .append(window.unavailableReason?.let { "\"${it.code}\"" } ?: "null").append(',')
            append("\"unavailableReasonCounts\":")
                .append(jsonCounts(window.reasonCounts.mapKeys { it.key.code }))
            append('}')
        }
        append("]}")
    }

    private fun jsonAxis(stats: ClassroomAxisStats?): String = stats?.let {
        "{\"mean\":${decimal(it.mean)},\"standardDeviation\":${decimal(it.standardDeviation)}," +
            "\"min\":${decimal(it.min)},\"max\":${decimal(it.max)},\"samples\":${it.samples}}"
    } ?: "null"

    private fun jsonCounts(counts: Map<String, Int>): String = counts.entries.joinToString(
        prefix = "{",
        postfix = "}",
    ) { "\"${jsonEscape(it.key)}\":${it.value}" }

    private fun decimal(value: Double?): String =
        value?.let { String.format(Locale.US, "%.3f", it) } ?: ""

    private fun csvEscape(value: String): String {
        if (value.isEmpty()) return ""
        val quoted = value.contains(',') || value.contains('"') || value.contains('\n')
        val escaped = value.replace("\"", "\"\"")
        return if (quoted) "\"$escaped\"" else escaped
    }

    private fun jsonEscape(value: String): String = value
        .replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
}

/**
 * 仅 Debug 构建可用的本地复盘文件写入。文件落在应用私有 cache，由用户主动分享；
 * Release 构建即使被误调用也会直接失败，不会产生文件。
 */
object ClassroomObservationDebugExporter {
    private const val MAX_EXPORT_FILES = 20

    fun write(
        context: Context,
        format: ClassroomObservationExportFormat,
        windows: List<ClassroomObservationWindow>,
    ): Uri {
        check(BuildConfig.DEBUG) { "课堂观察复盘导出只在 Debug 构建可用" }
        require(windows.isNotEmpty()) { "没有可导出的课堂观察窗口" }

        val directory = File(context.cacheDir, "classroom-observation").apply { mkdirs() }
        prune(directory)
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val file = File(directory, "classroom-observation-$stamp.${format.extension}")
        file.writeText(ClassroomObservationExport.encode(format, windows))
        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.coursefiles",
            file,
        )
    }

    private fun prune(directory: File) {
        val files = directory.listFiles()?.sortedByDescending { it.lastModified() }.orEmpty()
        files.drop(MAX_EXPORT_FILES).forEach { runCatching { it.delete() } }
    }
}
