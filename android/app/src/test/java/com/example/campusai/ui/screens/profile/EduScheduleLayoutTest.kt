package com.example.campusai.ui.screens.profile

import com.example.campusai.data.remote.EduScheduleItemDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EduScheduleLayoutTest {
    @Test
    fun layoutUsesAtLeastTwelveSectionsAndExpandsForLateClasses() {
        val result = layoutScheduleItems(
            listOf(
                EduScheduleItemDto(course_name = "早课", weekday = 1, start_section = 1, end_section = 2),
                EduScheduleItemDto(course_name = "夜课", weekday = 6, start_section = 13, end_section = 14),
            )
        )

        assertEquals(14, result.maxSection)
        assertEquals(2, result.placements[1].durationSections)
    }

    @Test
    fun layoutSkipsInvalidCoordinatesWithoutThrowing() {
        val result = layoutScheduleItems(
            listOf(
                EduScheduleItemDto(course_name = "坏星期", weekday = 8, start_section = 1, end_section = 2),
                EduScheduleItemDto(course_name = "坏节次", weekday = 2, start_section = 0, end_section = 2),
                EduScheduleItemDto(course_name = "正常", weekday = 3, start_section = 11, end_section = 12),
            )
        )

        assertEquals(1, result.placements.size)
        assertEquals("正常", result.placements.single().item.course_name)
    }

    @Test
    fun overlappingItemsArePlacedInSeparateStableLanes() {
        val result = layoutScheduleItems(
            listOf(
                EduScheduleItemDto(course_name = "A", weekday = 3, start_section = 3, end_section = 4),
                EduScheduleItemDto(course_name = "B", weekday = 3, start_section = 3, end_section = 4),
                EduScheduleItemDto(course_name = "C", weekday = 3, start_section = 5, end_section = 6),
            )
        )

        val overlapping = result.placements.take(2)
        assertEquals(listOf(0, 1), overlapping.map { it.lane })
        assertTrue(overlapping.all { it.laneCount == 2 })
        assertEquals(1, result.placements[2].laneCount)
    }
}
