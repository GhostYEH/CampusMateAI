package com.example.campusai

import com.example.campusai.data.model.ClassroomQuery
import com.example.campusai.data.repository.LocalClassroomRepository
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

class LocalClassroomRepositoryTest {

    private val zone: ZoneId = ZoneId.of("Asia/Shanghai")
    private val fixedNow: Long = LocalDate.of(2026, 8, 3) // 周一
        .atStartOfDay(zone).toInstant().toEpochMilli()

    private val repo = LocalClassroomRepository(now = { fixedNow })

    @Test
    fun `校区与教学楼数据完整`() {
        val campuses = repo.campuses()
        assertTrue(campuses.size >= 2)
        campuses.forEach { campus ->
            assertTrue(repo.buildings(campus).isNotEmpty())
        }
        assertEquals(5, repo.slots().size)
    }

    @Test
    fun `查询条件不完整时抛出异常`() {
        runBlocking {
            val incomplete = ClassroomQuery(campus = "主校区", building = null, date = null)
            assertFalse(incomplete.isComplete())
            var thrown = false
            try {
                repo.query(incomplete)
            } catch (_: IllegalArgumentException) {
                thrown = true
            }
            assertTrue(thrown)
        }
    }

    @Test
    fun `空闲节次等于全天减去占用`() = runBlocking {
        val monday = LocalDate.of(2026, 8, 3).toString()
        val results = repo.query(
            ClassroomQuery(campus = "主校区", building = "博学楼", date = monday),
        )
        assertTrue(results.isNotEmpty())
        results.forEach { availability ->
            assertTrue(availability.freeSlots.isNotEmpty())
            availability.freeSlots.forEach { slot ->
                // 周一博学楼 101 占用 1,2,3 节
                if (availability.classroom.id == "bx-101") {
                    assertTrue(slot.index !in listOf(1, 2, 3))
                }
            }
        }
    }

    @Test
    fun `容量与多媒体筛选生效`() = runBlocking {
        val date = LocalDate.of(2026, 8, 3).toString()
        val results = repo.query(
            ClassroomQuery(
                campus = "主校区",
                building = "博学楼",
                date = date,
                minCapacity = 100,
                multimediaOnly = true,
            ),
        )
        assertTrue(results.all { it.classroom.capacity >= 100 })
        assertTrue(results.all { it.classroom.hasMultimedia })
    }

    @Test
    fun `指定节次筛选生效`() = runBlocking {
        val date = LocalDate.of(2026, 8, 3).toString()
        val results = repo.query(
            ClassroomQuery(
                campus = "主校区",
                building = "博学楼",
                date = date,
                slotIndexes = setOf(5),
            ),
        )
        assertTrue(results.all { it.freeSlots.all { slot -> slot.index == 5 } })
    }

    @Test
    fun `可选日期为未来七天`() {
        val dates = repo.availableDates(fixedNow)
        assertEquals(7, dates.size)
        assertEquals(LocalDate.of(2026, 8, 3), dates.first())
        assertEquals(
            LocalDate.of(2026, 8, 3).dayOfWeek,
            Instant.ofEpochMilli(fixedNow).atZone(zone).toLocalDate().dayOfWeek,
        )
    }
}
