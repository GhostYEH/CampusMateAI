package com.example.campusai.data.model

/** 节次时间段，全校统一。 */
data class TimeSlot(val index: Int, val label: String, val timeRange: String)

/** 教室基础信息。 */
data class Classroom(
    val id: String,
    val name: String,
    val campus: String,
    val building: String,
    val floor: Int,
    val capacity: Int,
    val hasMultimedia: Boolean,
)

/** 某教室在某天的空闲情况。 */
data class ClassroomAvailability(
    val classroom: Classroom,
    val freeSlots: List<TimeSlot>,
)

/** 空教室查询条件；campus / building / date 为空表示尚未选择。 */
data class ClassroomQuery(
    val campus: String? = null,
    val building: String? = null,
    val date: String? = null,
    val slotIndexes: Set<Int> = emptySet(),
    val minCapacity: Int = 0,
    val multimediaOnly: Boolean = false,
) {
    /** 基础条件是否完整（校区 / 教学楼 / 日期必选）。 */
    fun isComplete(): Boolean =
        !campus.isNullOrBlank() && !building.isNullOrBlank() && !date.isNullOrBlank()
}
