package com.example.campusai.ui.screens.profile

import com.example.campusai.data.remote.EduScheduleItemsResponse
import com.example.campusai.data.remote.EduSyncResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EduSyncCoordinatorTest {
    @Test
    fun syncsScheduleGradeAndExamAndVerifiesStoredSchedule() = runBlocking {
        val calls = mutableListOf<String>()

        val result = syncAllEduData(
            syncSchedule = {
                calls += "schedule"
                EduSyncResult(
                    sync_type = "schedule",
                    status = "success",
                    items_count = 2,
                    persisted = true,
                )
            },
            readSchedule = {
                calls += "read_schedule"
                EduScheduleItemsResponse(items_count = 2)
            },
            syncGrade = {
                calls += "grade"
                EduSyncResult(sync_type = "grade", status = "success", items_count = 1, persisted = true)
            },
            syncExam = {
                calls += "exam"
                EduSyncResult(sync_type = "exam", status = "success", items_count = 1, persisted = true)
            },
        )

        assertEquals(listOf("schedule", "read_schedule", "grade", "exam"), calls)
        assertTrue(result.scheduleResult?.status == "success")
        assertTrue(result.gradeResult?.status == "success")
        assertTrue(result.examResult?.status == "success")
    }

    @Test
    fun marksScheduleFailedWhenBackendDidNotPersistIt() = runBlocking {
        val result = syncAllEduData(
            syncSchedule = {
                EduSyncResult(
                    sync_type = "schedule",
                    status = "success",
                    items_count = 2,
                    persisted = false,
                )
            },
            readSchedule = { EduScheduleItemsResponse(items_count = 2) },
            syncGrade = { null },
            syncExam = { null },
        )

        assertEquals("failed", result.scheduleResult?.status)
        assertTrue(result.scheduleResult?.previous_schedule_preserved == true)
        assertEquals("课表未成功导入系统，请重新同步；原有课表未被覆盖", eduScheduleStatusMessage(result.scheduleResult))
    }

    @Test
    fun keepsBackendValidationFailureAndPreservationDiagnostic() = runBlocking {
        val result = syncAllEduData(
            syncSchedule = {
                EduSyncResult(
                    sync_type = "schedule",
                    status = "failed",
                    error_message = "课表结构校验失败",
                    stage = "validate",
                    previous_schedule_preserved = true,
                    protocol_source = "live_discovered",
                )
            },
            readSchedule = { error("failed schedule must not be read back") },
            syncGrade = { null },
            syncExam = { null },
        )

        assertEquals("failed", result.scheduleResult?.status)
        assertEquals("validate", result.scheduleResult?.stage)
        assertEquals("课表校验失败：课表结构校验失败；原有课表未被覆盖", eduScheduleStatusMessage(result.scheduleResult))
    }

    @Test
    fun acceptsVerifiedExplicitEmptyScheduleAfterReadBack() = runBlocking {
        var requestedSemester: String? = null
        val result = syncAllEduData(
            syncSchedule = {
                EduSyncResult(
                    sync_type = "schedule",
                    status = "success",
                    items_count = 0,
                    persisted = true,
                    stage = "commit",
                    semester = "2025-2026-1",
                )
            },
            readSchedule = {
                requestedSemester = it
                EduScheduleItemsResponse(items_count = 0)
            },
            syncGrade = { null },
            syncExam = { null },
        )

        assertEquals("success", result.scheduleResult?.status)
        assertEquals("2025-2026-1", requestedSemester)
        assertEquals("课表同步成功，本学期暂无课程", eduScheduleStatusMessage(result.scheduleResult))
    }
}
