package com.example.campusai.data.focus

import com.example.campusai.data.behavior.BehaviorDisplayState
import com.example.campusai.data.behavior.PresenceState
import com.example.campusai.data.behavior.StudyBehavior

/**
 * 共同课堂使用的粗粒度专注状态。
 * 只描述“当前能否观察到学习行为/是否还在座位上”，不作为专注度评分或心理判断。
 */
enum class ClassroomAttentionState {
    FOCUSED,
    POSSIBLY_DISTRACTED,
    DISTRACTED,
    AWAY,
    UNKNOWN,
}

data class ClassroomAttention(
    val state: ClassroomAttentionState = ClassroomAttentionState.UNKNOWN,
    val sinceMs: Long = 0L,
    val updatedAtMs: Long = 0L,
)

data class ClassroomAttentionConfig(
    val stabilityMs: Long = 5_000,
)

/**
 * 把已有的端侧观察转成课堂可上报的粗粒度状态，并做 5 秒防抖：
 * 一次误判不会立刻让老师看到“分心”，持续状态才会切换。
 */
class ClassroomAttentionTracker(
    private val config: ClassroomAttentionConfig = ClassroomAttentionConfig(),
) {
    private var current = ClassroomAttentionState.UNKNOWN
    private var sinceMs = 0L
    private var candidate = ClassroomAttentionState.UNKNOWN
    private var candidateSinceMs = 0L
    private var hasSignal = false

    fun process(
        displayState: BehaviorDisplayState?,
        presence: PresenceState,
        focusState: FocusState,
        timestampMs: Long,
    ): ClassroomAttention {
        val observed = classify(displayState, presence, focusState)
        if (!hasSignal) {
            hasSignal = true
            current = observed
            candidate = observed
            sinceMs = timestampMs
            candidateSinceMs = timestampMs
            return snapshot(timestampMs)
        }
        if (observed != candidate) {
            candidate = observed
            candidateSinceMs = timestampMs
        }
        if (candidate != current && timestampMs - candidateSinceMs >= config.stabilityMs) {
            current = candidate
            sinceMs = timestampMs
        }
        return snapshot(timestampMs)
    }

    fun reset() {
        current = ClassroomAttentionState.UNKNOWN
        candidate = ClassroomAttentionState.UNKNOWN
        sinceMs = 0L
        candidateSinceMs = 0L
        hasSignal = false
    }

    private fun snapshot(timestampMs: Long) = ClassroomAttention(current, sinceMs, timestampMs)

    private fun classify(
        displayState: BehaviorDisplayState?,
        presence: PresenceState,
        focusState: FocusState,
    ): ClassroomAttentionState {
        if (presence == PresenceState.ABSENT || focusState == FocusState.NO_FACE) {
            return ClassroomAttentionState.AWAY
        }
        if (displayState is BehaviorDisplayState.Stable) {
            return when (displayState.behavior) {
                StudyBehavior.PHONE_USE, StudyBehavior.PHONE_PICKUP ->
                    ClassroomAttentionState.DISTRACTED
                StudyBehavior.DROWSY, StudyBehavior.SLEEPING, StudyBehavior.HEAD_DOWN ->
                    ClassroomAttentionState.DISTRACTED
                StudyBehavior.IDLE, StudyBehavior.LOOKING_AWAY ->
                    ClassroomAttentionState.POSSIBLY_DISTRACTED
                StudyBehavior.VISIBLE_STUDY, StudyBehavior.READING,
                StudyBehavior.WRITING, StudyBehavior.COMPUTER, StudyBehavior.TYPING ->
                    ClassroomAttentionState.FOCUSED
                else -> if (focusState == FocusState.BREAK_SUGGESTED) {
                    ClassroomAttentionState.POSSIBLY_DISTRACTED
                } else {
                    ClassroomAttentionState.UNKNOWN
                }
            }
        }
        return if (focusState == FocusState.BREAK_SUGGESTED) {
            ClassroomAttentionState.POSSIBLY_DISTRACTED
        } else {
            ClassroomAttentionState.UNKNOWN
        }
    }
}
