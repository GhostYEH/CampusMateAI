package com.example.campusai.ui.screens.profile

import com.example.campusai.data.remote.EduScheduleItemsResponse
import com.example.campusai.data.remote.EduSyncResult

data class EduSyncBatchResult(
    val scheduleResult: EduSyncResult?,
    val gradeResult: EduSyncResult?,
    val examResult: EduSyncResult?,
)

private val syncStageLabels = mapOf(
    "protocol_discovery" to "课表协议识别",
    "fetch" to "课表读取",
    "parse" to "课表解析",
    "validate" to "课表校验",
    "commit" to "课表保存",
)

fun eduScheduleStatusMessage(result: EduSyncResult?): String {
    if (result == null) return "课表同步失败，请稍后重试"
    if (result.status == "success") {
        return if (result.items_count == 0) "课表同步成功，本学期暂无课程"
        else "课表同步成功，已校验并保存 ${result.items_count} 条课程记录"
    }
    val stage = result.stage?.let { syncStageLabels[it] ?: "课表同步" }
    val detail = result.error_message ?: "请稍后重试"
    val preserved = if (result.previous_schedule_preserved == true) "；原有课表未被覆盖" else ""
    return "${stage?.let { "${it}失败：" } ?: ""}$detail$preserved"
}

suspend fun syncAllEduData(
    syncSchedule: suspend () -> EduSyncResult?,
    readSchedule: suspend (String?) -> EduScheduleItemsResponse?,
    syncGrade: suspend () -> EduSyncResult?,
    syncExam: suspend () -> EduSyncResult?,
    onProgress: (String) -> Unit = {},
): EduSyncBatchResult {
    onProgress("正在同步课表…")
    val rawSchedule = syncSchedule()
    val storedSchedule = rawSchedule?.takeIf { it.status == "success" }
        ?.let { readSchedule(it.schedule?.semester ?: it.semester) }
    val scheduleResult = rawSchedule?.let {
        if (it.status != "success" || isScheduleImported(it, storedSchedule)) it
        else it.copy(
            status = "failed",
            error_message = "课表未成功导入系统，请重新同步",
            previous_schedule_preserved = true,
        )
    }

    onProgress("正在同步成绩…")
    val gradeResult = syncGrade()
    onProgress("正在同步考试安排…")
    val examResult = syncExam()
    return EduSyncBatchResult(scheduleResult, gradeResult, examResult)
}
