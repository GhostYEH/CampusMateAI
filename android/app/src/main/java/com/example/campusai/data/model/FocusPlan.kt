package com.example.campusai.data.model

enum class FocusPlanStepStatus {
    PENDING,
    COMPLETED,
}

data class FocusPlanStep(
    val stepNumber: Int,
    val title: String,
    val description: String,
    val estimatedMinutes: Int,
    val completionCriteria: String,
    val dependencies: List<Int> = emptyList(),
    val isPolicyStep: Boolean = false,
    val knowledgeSource: String? = null,
    val status: FocusPlanStepStatus = FocusPlanStepStatus.PENDING,
)

data class FocusPlan(
    val taskId: String,
    val taskTitle: String,
    val goal: String,
    val steps: List<FocusPlanStep>,
    val updatedAtEpochMillis: Long = 0L,
    val pendingStepCompletionSessionId: String? = null,
    val pendingStepCompletionStepNumber: Int? = null,
    val taskCompletionPending: Boolean = false,
) {
    val currentStep: FocusPlanStep?
        get() = steps.firstOrNull { it.status == FocusPlanStepStatus.PENDING }

    val isComplete: Boolean
        get() = steps.isNotEmpty() && steps.all { it.status == FocusPlanStepStatus.COMPLETED }

    fun completeCurrentStep(): FocusPlan {
        val current = currentStep ?: return this
        return completeStep(current.stepNumber)
    }

    fun completeStep(stepNumber: Int): FocusPlan {
        val updatedSteps = steps.map { step ->
            if (step.stepNumber == stepNumber) {
                step.copy(status = FocusPlanStepStatus.COMPLETED)
            } else {
                step
            }
        }
        return copy(
            steps = updatedSteps,
            updatedAtEpochMillis = System.currentTimeMillis(),
            taskCompletionPending = taskCompletionPending ||
                (updatedSteps.isNotEmpty() && updatedSteps.all { it.status == FocusPlanStepStatus.COMPLETED }),
        )
    }
}
