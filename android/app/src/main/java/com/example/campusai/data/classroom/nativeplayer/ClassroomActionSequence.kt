package com.example.campusai.data.classroom.nativeplayer

/**
 * 本页动作顺序：服务端 `steps` 只列出可同步执行的动作，按 `action_id` 对应到
 * `actions` 里的真实动作。这里只做纯数据解析，实际播放由 ViewModel 执行。
 */
data class ClassroomSequenceStep(
    val index: Int,
    val actionId: String,
    val type: String,
    val mode: String,
    val action: NativeAction?,
    val problem: String? = null,
) {
    val blocking: Boolean
        get() = mode != "fire_and_forget" && type !in FIRE_AND_FORGET_TYPES

    companion object {
        val FIRE_AND_FORGET_TYPES = setOf("spotlight", "laser")
    }
}

data class ClassroomSequencePlan(
    val sceneId: String,
    val steps: List<ClassroomSequenceStep> = emptyList(),
)

object ClassroomActionSequencePlanner {
    /**
     * 严格按服务端 steps 顺序保留动作；不把 actions 中没有进入 steps 的动作补进来，
     * 以保留服务端对 fire-and-forget / 不支持动作的语义。
     */
    fun plan(
        sceneId: String,
        steps: List<NativePlaybackStep>,
        actions: List<NativeAction>,
    ): ClassroomSequencePlan {
        val byId = actions.associateBy { it.id }
        return ClassroomSequencePlan(
            sceneId = sceneId,
            steps = steps.mapIndexed { index, step ->
                val action = byId[step.actionId]
                val effectiveType = step.type.ifBlank { action?.type.orEmpty() }
                val effectiveMode = if (effectiveType in ClassroomSequenceStep.FIRE_AND_FORGET_TYPES) {
                    "fire_and_forget"
                } else {
                    step.mode.ifBlank { "sync" }
                }
                ClassroomSequenceStep(
                    index = index,
                    actionId = step.actionId,
                    type = effectiveType,
                    mode = effectiveMode,
                    action = action,
                    problem = when {
                        step.actionId.isBlank() -> "顺序动作缺少 action_id。"
                        action == null -> "顺序动作 ${step.actionId} 没有对应的课堂动作。"
                        !action.supported -> action.reason?.takeIf { it.isNotBlank() }
                            ?: "动作 ${action.type} 当前不支持原生执行。"
                        effectiveType.isNotBlank() && effectiveType != action.type ->
                            "顺序动作 ${step.actionId} 的类型与下发动作不一致。"
                        else -> null
                    },
                )
            },
        )
    }
}

sealed interface ClassroomSequenceStepResult {
    data object Completed : ClassroomSequenceStepResult
    data class Failed(val reason: String) : ClassroomSequenceStepResult
}

sealed interface ClassroomSequenceResult {
    data object Completed : ClassroomSequenceResult
    data class Failed(val reason: String) : ClassroomSequenceResult
    data object Cancelled : ClassroomSequenceResult
}

/**
 * 顺序执行器：每个动作必须返回 Completed 才推进下一步。调用方在 [execute] 中
 * 等待真实音频/视频结束；暂停由 [awaitPause] 承担，取消由协程取消和 [isCurrent]
 * 共同承担。动作失败立即停止，不把后续步骤继续跑完。
 */
suspend fun runClassroomSequence(
    steps: List<ClassroomSequenceStep>,
    isCurrent: () -> Boolean,
    awaitPause: suspend () -> Unit,
    onStep: (Int, ClassroomSequenceStep) -> Unit,
    execute: suspend (ClassroomSequenceStep, awaitPause: suspend () -> Unit) -> ClassroomSequenceStepResult,
): ClassroomSequenceResult {
    if (steps.isEmpty()) return ClassroomSequenceResult.Completed
    for ((index, step) in steps.withIndex()) {
        if (!isCurrent()) return ClassroomSequenceResult.Cancelled
        awaitPause()
        if (!isCurrent()) return ClassroomSequenceResult.Cancelled
        onStep(index, step)
        when (val result = execute(step, awaitPause)) {
            ClassroomSequenceStepResult.Completed -> Unit
            is ClassroomSequenceStepResult.Failed -> return ClassroomSequenceResult.Failed(result.reason)
        }
        if (!isCurrent()) return ClassroomSequenceResult.Cancelled
    }
    return ClassroomSequenceResult.Completed
}
