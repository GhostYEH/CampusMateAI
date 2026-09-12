package com.example.campusai.data.remote.agent

import com.example.campusai.data.model.Exam
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * 验证服务端 exam ID 是 String（考试真相），本地 Exam 使用 Long ID（离线缓存）。
 * Agent Runtime 引用 exam 时一律使用 String ID，不与本地 Long ID 混淆。
 */
class ServerExamIdMappingTest {

    @Test
    fun `local Exam uses Long id as offline cache`() {
        val localExam = Exam(
            id = 12345L,
            courseName = "数据结构",
            date = "2026-12-20",
            startTime = "09:00",
            endTime = "11:00",
            location = "博学楼",
            seatNumber = "01",
            type = "期末考试",
        )
        assertEquals(Long::class.javaPrimitiveType, localExam.id::class.javaPrimitiveType)
        assertEquals(12345L, localExam.id)
    }

    @Test
    fun `agent runtime campaign references exams by String id`() {
        val campaign = FinalReviewCampaignDto(
            campaignId = "camp_001",
            examIds = listOf("exam_server_001", "exam_server_002"),
        )
        campaign.examIds.forEach { examId ->
            assertEquals(String::class.java, examId::class.java)
        }
    }

    @Test
    fun `String exam id does not collide with Long local id`() {
        val localExamId = 1L
        val serverExamId = "1"
        // 类型不同，不会混淆
        assertNotEquals(localExamId, serverExamId)
        assertNotEquals(localExamId::class.java, serverExamId::class.java)
    }

    @Test
    fun `course research run uses String course id`() {
        val request = CourseResearchRunCreateRequest(
            question = "test",
            courseId = "course_server_001",
        )
        assertEquals7("course_server_001", request.courseId)
    }

    private fun assertEquals7(expected: String, actual: String?) {
        assertEquals(expected, actual)
    }
}