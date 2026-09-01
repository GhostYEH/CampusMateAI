package com.example.campusai

import com.example.campusai.data.model.FocusPlanStepStatus
import com.example.campusai.data.remote.TaskBreakdownResponseDto
import com.example.campusai.data.remote.TaskBreakdownStepDto
import com.example.campusai.data.repository.toFocusPlan
import org.junit.Assert.assertEquals
import org.junit.Test

class FocusPlanMapperTest {
    @Test
    fun mapsServerStepsIntoAnOrderedPendingPlan() {
        val response = TaskBreakdownResponseDto(
            mode = "rule_fallback",
            goal = "复习数据结构",
            related_task_id = "task-1",
            related_task_title = "复习数据结构",
            steps = listOf(
                TaskBreakdownStepDto(2, "练习", "完成练习", 25, listOf(1), "练习完成"),
                TaskBreakdownStepDto(1, "准备", "打开资料", 10, emptyList(), "资料已打开"),
            ),
        )

        val plan = response.toFocusPlan("task-1", "备用标题")

        assertEquals(listOf(1, 2), plan.steps.map { it.stepNumber })
        assertEquals("复习数据结构", plan.taskTitle)
        assertEquals(FocusPlanStepStatus.PENDING, plan.currentStep?.status)
        assertEquals(listOf(1), plan.steps[1].dependencies)
    }
}
