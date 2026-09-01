package com.example.campusai.data.repository

import com.example.campusai.data.model.FocusPlan
import com.example.campusai.data.model.FocusPlanStep
import com.example.campusai.data.remote.TaskBreakdownResponseDto

internal fun TaskBreakdownResponseDto.toFocusPlan(
    taskId: String,
    taskTitle: String,
): FocusPlan = FocusPlan(
    taskId = taskId,
    taskTitle = related_task_title?.ifBlank { null } ?: taskTitle,
    goal = goal,
    steps = steps.sortedBy { it.step_number }.map { step ->
        FocusPlanStep(
            stepNumber = step.step_number,
            title = step.title,
            description = step.description,
            estimatedMinutes = step.estimated_minutes,
            completionCriteria = step.completion_criteria,
            dependencies = step.dependencies,
            isPolicyStep = step.is_policy_step,
            knowledgeSource = step.knowledge_source,
        )
    },
)
