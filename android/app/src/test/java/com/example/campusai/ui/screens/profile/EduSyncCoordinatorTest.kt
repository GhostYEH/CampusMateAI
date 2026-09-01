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
    }
}
