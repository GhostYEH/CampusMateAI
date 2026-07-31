package com.example.campusai

import com.example.campusai.data.local.InMemoryKeyValueStorage
import com.example.campusai.data.model.Exam
import com.example.campusai.data.model.ExamStatus
import com.example.campusai.data.repository.LocalExamRepository
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class LocalExamRepositoryTest {

    private val zone: ZoneId = ZoneId.of("Asia/Shanghai")
    private val fixedNow: Long = LocalDateTime.of(2026, 7, 31, 12, 0)
        .atZone(zone).toInstant().toEpochMilli()

    private fun newRepo(storage: InMemoryKeyValueStorage = InMemoryKeyValueStorage()) =
        LocalExamRepository(
            storage = storage,
            courseNames = { listOf("数据结构", "高等数学（下）") },
            now = { fixedNow },
        )

    private fun examAt(daysOffset: Long, id: Long = 1L): Exam {
        val date = Instant.ofEpochMilli(fixedNow).atZone(zone).toLocalDate().plusDays(daysOffset)
        return Exam(
            id = id,
            courseName = "数据结构",
            date = date.format(DateTimeFormatter.ISO_LOCAL_DATE),
            startTime = "09:00",
            endTime = "11:00",
            location = "博学楼 1-401",
            seatNumber = "06",
            type = "期末考试",
        )
    }

    @Test
    fun `首次加载生成基于课程的种子数据`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val exams = repo.exams.value
        assertTrue(exams.isNotEmpty())
        assertTrue(exams.any { it.courseName == "数据结构" })
        assertTrue(exams.any { it.courseName == "高等数学（下）" })
    }

    @Test
    fun `新增与编辑考试`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val before = repo.exams.value.size
        val id = repo.upsert(examAt(5, id = 0L))
        assertEquals(before + 1, repo.exams.value.size)
        assertNotNull(repo.getById(id))

        repo.upsert(examAt(6, id = id).copy(location = "明德楼 3-208"))
        assertEquals(before + 1, repo.exams.value.size)
        assertEquals("明德楼 3-208", repo.getById(id)?.location)
    }

    @Test
    fun `删除考试`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val id = repo.upsert(examAt(5, id = 0L))
        repo.delete(id)
        assertNull(repo.getById(id))
    }

    @Test
    fun `考试提醒开关`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val id = repo.upsert(examAt(5, id = 0L))
        repo.setReminder(id, false)
        assertFalse(repo.getById(id)?.reminderEnabled ?: true)
    }

    @Test
    fun `数据在重建仓库后保持`() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repo = newRepo(storage)
        repo.refresh()
        val id = repo.upsert(examAt(5, id = 0L))

        val restored = newRepo(storage)
        restored.refresh()
        assertNotNull(restored.getById(id))
    }

    @Test
    fun `状态与倒计时计算`() {
        val future = examAt(3)
        assertEquals(ExamStatus.UPCOMING, future.statusAt(fixedNow, zone))
        assertEquals(3L, future.daysUntil(fixedNow, zone))

        val past = examAt(-2)
        assertEquals(ExamStatus.ENDED, past.statusAt(fixedNow, zone))
        assertNull(past.daysUntil(fixedNow, zone))

        val today = examAt(0).copy(startTime = "08:00", endTime = "10:00")
        // 固定时间为当天 12:00，考试已结束
        assertEquals(ExamStatus.ENDED, today.statusAt(fixedNow, zone))
    }

    @Test
    fun `非法时间字符串不会崩溃`() {
        val broken = examAt(1).copy(date = "not-a-date")
        assertEquals(ExamStatus.ENDED, broken.statusAt(fixedNow, zone))
        assertNull(broken.daysUntil(fixedNow, zone))
        assertEquals("not-a-date", broken.dateLabel())
    }
}
