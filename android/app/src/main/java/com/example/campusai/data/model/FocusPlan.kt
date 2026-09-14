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
    val knowledgeDocumentId: String? = null,
    val knowledgeStatus: String? = null,
    val status: FocusPlanStepStatus = FocusPlanStepStatus.PENDING,
) {
    /** 展示用的前置步骤说明,例如「需先完成第 1、2 步」。 */
    val prerequisiteHint: String?
        get() = dependencies.sorted().takeIf { it.isNotEmpty() }
            ?.joinToString("、") { it.toString() }
            ?.let { "需先完成第 $it 步" }

    /** 政策步骤但知识库证据不足,需要用户向辅导员或相关部门确认。 */
    val needsKnowledgeConfirmation: Boolean
        get() = isPolicyStep && knowledgeSource.isNullOrBlank() &&
            (knowledgeStatus == null || knowledgeStatus == "needs_confirmation")

    /** 展示用的政策来源说明;无来源时给出可执行的确认提示。 */
    val knowledgeHint: String?
        get() = when {
            !knowledgeSource.isNullOrBlank() -> "参考：$knowledgeSource"
            needsKnowledgeConfirmation -> "政策相关,暂无权威资料,建议先向辅导员确认"
            else -> null
        }
}

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
