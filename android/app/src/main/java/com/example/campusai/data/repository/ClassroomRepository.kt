package com.example.campusai.data.repository

import com.example.campusai.data.model.Classroom
import com.example.campusai.data.model.ClassroomAvailability
import com.example.campusai.data.model.ClassroomQuery
import com.example.campusai.data.model.TimeSlot
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

/**
 * 空教室数据入口。当前根据内置课程占用表计算空闲节次，
 * 后续接入教务排课数据时替换为 Remote 实现即可。
 */
interface ClassroomRepository {
    val loading: StateFlow<Boolean>
    val error: StateFlow<String?>

    fun campuses(): List<String>
    fun buildings(campus: String): List<String>
    fun slots(): List<TimeSlot>
    fun availableDates(nowMillis: Long): List<LocalDate>

    /** 查询空闲教室；[ClassroomQuery.isComplete] 为 false 时抛出 [IllegalArgumentException]。 */
    suspend fun query(query: ClassroomQuery): List<ClassroomAvailability>
}

class LocalClassroomRepository(
    private val now: () -> Long = System::currentTimeMillis,
) : ClassroomRepository {

    private val _loading = MutableStateFlow(false)
    override val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    override val error: StateFlow<String?> = _error.asStateFlow()

    override fun campuses(): List<String> = campusData.map { it.name }

    override fun buildings(campus: String): List<String> =
        campusData.firstOrNull { it.name == campus }?.buildings?.map { it.name }.orEmpty()

    override fun slots(): List<TimeSlot> = allSlots

    override fun availableDates(nowMillis: Long): List<LocalDate> {
        val zone = ZoneId.systemDefault()
        val today = Instant.ofEpochMilli(nowMillis).atZone(zone).toLocalDate()
        return (0L..6L).map { today.plusDays(it) }
    }

    override suspend fun query(query: ClassroomQuery): List<ClassroomAvailability> =
        withContext(Dispatchers.Default) {
            require(query.isComplete()) { "查询条件不完整" }
            _loading.value = true
            _error.value = null
            try {
                // 模拟一次本地计算耗时，驱动页面加载状态
                delay(250)
                val date = LocalDate.parse(query.date!!)
                val dayOfWeek = date.dayOfWeek.value // 1..7
                val building = campusData
                    .firstOrNull { it.name == query.campus }
                    ?.buildings
                    ?.firstOrNull { it.name == query.building }
                    ?: throw IllegalStateException("未找到对应教学楼")
                building.classrooms
                    .filter { it.capacity >= query.minCapacity }
                    .filter { !query.multimediaOnly || it.hasMultimedia }
                    .map { room ->
                        val occupied = occupiedSlots(room, dayOfWeek)
                        val free = allSlots.filter { slot ->
                            slot.index !in occupied &&
                                (query.slotIndexes.isEmpty() || slot.index in query.slotIndexes)
                        }
                        ClassroomAvailability(room, free)
                    }
                    .filter { it.freeSlots.isNotEmpty() }
                    .sortedWith(compareBy({ it.classroom.floor }, { it.classroom.name }))
            } catch (e: IllegalArgumentException) {
                throw e
            } catch (_: Exception) {
                _error.value = "查询失败，请稍后重试"
                emptyList()
            } finally {
                _loading.value = false
            }
        }

    /** 由课程占用表推算某天（按星期几）的占用节次。 */
    private fun occupiedSlots(room: Classroom, dayOfWeek: Int): Set<Int> {
        val fixed = weeklyOccupancy[room.id]?.get(dayOfWeek).orEmpty()
        return fixed.toSet()
    }

    private data class BuildingData(val name: String, val classrooms: List<Classroom>)
    private data class CampusData(val name: String, val buildings: List<BuildingData>)

    companion object {
        /** 全天五个大节次。 */
        val allSlots = listOf(
            TimeSlot(1, "第 1-2 节", "08:00-09:40"),
            TimeSlot(2, "第 3-4 节", "10:00-11:40"),
            TimeSlot(3, "第 5-6 节", "14:00-15:40"),
            TimeSlot(4, "第 7-8 节", "16:00-17:40"),
            TimeSlot(5, "第 9-10 节", "19:00-20:40"),
        )

        private fun room(
            id: String, name: String, campus: String, building: String,
            floor: Int, capacity: Int, multimedia: Boolean,
        ) = Classroom(id, name, campus, building, floor, capacity, multimedia)

        private val campusData = listOf(
            CampusData(
                "主校区",
                listOf(
                    BuildingData(
                        "博学楼",
                        listOf(
                            room("bx-101", "博学楼 101", "主校区", "博学楼", 1, 120, true),
                            room("bx-203", "博学楼 203", "主校区", "博学楼", 2, 80, true),
                            room("bx-305", "博学楼 305", "主校区", "博学楼", 3, 45, false),
                            room("bx-401", "博学楼 401", "主校区", "博学楼", 4, 60, true),
                        ),
                    ),
                    BuildingData(
                        "明德楼",
                        listOf(
                            room("md-102", "明德楼 102", "主校区", "明德楼", 1, 90, true),
                            room("md-208", "明德楼 208", "主校区", "明德楼", 2, 40, false),
                            room("md-310", "明德楼 310", "主校区", "明德楼", 3, 55, true),
                        ),
                    ),
                ),
            ),
            CampusData(
                "东校区",
                listOf(
                    BuildingData(
                        "实验楼 A 栋",
                        listOf(
                            room("sya-201", "实验楼 A-201", "东校区", "实验楼 A 栋", 2, 70, true),
                            room("sya-302", "实验楼 A-302", "东校区", "实验楼 A 栋", 3, 36, false),
                        ),
                    ),
                    BuildingData(
                        "教学楼 C 栋",
                        listOf(
                            room("jxc-105", "教学楼 C-105", "东校区", "教学楼 C 栋", 1, 110, true),
                            room("jxc-206", "教学楼 C-206", "东校区", "教学楼 C 栋", 2, 50, true),
                            room("jxc-404", "教学楼 C-404", "东校区", "教学楼 C 栋", 4, 42, false),
                        ),
                    ),
                ),
            ),
        )

        /**
         * 课程占用表：教室 -> (星期几 -> 占用节次)。
         * 数据来自本学期课程安排（演示数据），同一星期几的占用保持一致。
         */
        private val weeklyOccupancy: Map<String, Map<Int, List<Int>>> = mapOf(
            "bx-101" to mapOf(1 to listOf(1, 2, 3), 2 to listOf(1, 4), 3 to listOf(2, 3), 4 to listOf(1, 2), 5 to listOf(1, 3, 5)),
            "bx-203" to mapOf(1 to listOf(2), 2 to listOf(2, 3), 3 to listOf(1, 4), 4 to listOf(3), 5 to listOf(2, 4)),
            "bx-305" to mapOf(1 to listOf(1, 3), 3 to listOf(3, 5), 5 to listOf(1, 2)),
            "bx-401" to mapOf(2 to listOf(1, 2, 3), 4 to listOf(2, 3, 4), 6 to listOf(1)),
            "md-102" to mapOf(1 to listOf(3, 4), 2 to listOf(1), 3 to listOf(1, 2, 5), 5 to listOf(3)),
            "md-208" to mapOf(1 to listOf(1, 2), 4 to listOf(1, 5), 6 to listOf(2, 3)),
            "md-310" to mapOf(2 to listOf(4, 5), 3 to listOf(2), 5 to listOf(1, 2, 3)),
            "sya-201" to mapOf(1 to listOf(2, 3, 4), 3 to listOf(1, 2), 4 to listOf(4)),
            "sya-302" to mapOf(2 to listOf(1, 3), 5 to listOf(2, 5), 6 to listOf(1, 2, 3)),
            "jxc-105" to mapOf(1 to listOf(1, 5), 2 to listOf(2, 4), 4 to listOf(1, 2, 3)),
            "jxc-206" to mapOf(3 to listOf(1, 3, 4), 5 to listOf(1), 6 to listOf(3, 4)),
            "jxc-404" to mapOf(1 to listOf(4), 4 to listOf(2), 5 to listOf(3, 4, 5)),
        )
    }
}
