package com.example.campusai.data.focus.goal

import com.example.campusai.data.remote.TaskBreakdownResponseDto
import com.example.campusai.data.remote.TaskBreakdownStepDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusGoalPlanTest {
    @Test
    fun mapsAndSortsBreakdownStepsIntoAnActionablePlan() {
        val plan = TaskBreakdownResponseDto(
            mode = "llm",
            goal = "完成期末复习",
            steps = listOf(
                TaskBreakdownStepDto(2, "刷题", "完成一套题", 30, completion_criteria = "错题已标记"),
                TaskBreakdownStepDto(1, "整理范围", "列出章节", 10, completion_criteria = "章节清单已完成"),
            ),
        ).toFocusGoalPlan()

        assertEquals(listOf(1, 2), plan.steps.map { it.number })
        assertEquals("整理范围", plan.steps.first().title)
        assertTrue(plan.analysis.contains("2 步"))
        assertTrue(plan.analysis.contains("整理范围"))
    }
}
