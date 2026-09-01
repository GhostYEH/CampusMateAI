package com.example.campusai.ui.screens.profile

import com.example.campusai.data.remote.EduScheduleItemsResponse
import com.example.campusai.data.remote.EduSyncResult

data class EduSyncBatchResult(
    val scheduleResult: EduSyncResult?,
    val gradeResult: EduSyncResult?,
    val examResult: EduSyncResult?,
)

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
        ?.let { readSchedule(it.schedule?.semester) }
    val scheduleResult = rawSchedule?.let {
        if (isScheduleImported(it, storedSchedule)) it
        else it.copy(status = "failed", error_message = "课表未成功导入系统，请重新同步")
    }

    onProgress("正在同步成绩…")
    val gradeResult = syncGrade()
    onProgress("正在同步考试安排…")
    val examResult = syncExam()
    return EduSyncBatchResult(scheduleResult, gradeResult, examResult)
}
