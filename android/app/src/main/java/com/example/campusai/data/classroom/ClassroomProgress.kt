package com.example.campusai.data.classroom

import com.example.campusai.data.remote.InteractiveClassroomGenerateResponse
import com.example.campusai.data.remote.InteractiveClassroomSessionDto

/**
 * 互动课堂生成进度（课程详情侧）。
 *
 * OpenMAIC 的真实 job 状态只有 `queued / running / succeeded / failed`，
 * 没有 cancel。所以 UI 只能"停止查看进度"，不能给学生一个假的"取消"。
 */
enum class ClassroomPhase {
    IDLE,
    REQUESTING,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    FAILED,
}

data class ClassroomProgressState(
    val phase: ClassroomPhase = ClassroomPhase.IDLE,
    val sessionId: String? = null,
    val mode: String? = null,
    val requestedMode: String? = null,
    val adaptiveReason: String? = null,
    val step: String = "",
    val progress: Int = 0,
    val message: String = "",
    val updatedAt: String? = null,
    val publicUrl: String? = null,
    val urlUnavailableReason: String? = null,
    /** 学生指定的资料里有无法使用的（不存在 / 已删除 / 越权）时的说明。 */
    val materialsWarning: String? = null,
    /** 本次个性化来源说明（旧任务没有快照时会明确告知）。 */
    val requestSourceNote: String? = null,
    val errorCode: String? = null,
    val retryable: Boolean = false,
    val partial: Boolean = false,
    val error: String = "",
) {
    val isLive: Boolean get() = phase == ClassroomPhase.QUEUED || phase == ClassroomPhase.RUNNING

    /** 已成功但**没有**可打开的公开地址（未配置 OPENMAIC_EMBED_ORIGIN）。 */
    val generatedButClosed: Boolean
        get() = phase == ClassroomPhase.SUCCEEDED && publicUrl.isNullOrBlank()

    /**
     * 只有拿到经过校验的公开地址才允许"打开"。
     * 绝不回落到内部服务地址 —— 内部地址既不该泄露，也一定打不开。
     */
    fun openableUrl(): String? = publicUrl?.takeIf { it.isNotBlank() }
}

object ClassroomProgressReducer {

    fun fromGenerate(resp: InteractiveClassroomGenerateResponse): ClassroomProgressState {
        val session = resp.session
        return ClassroomProgressState(
            phase = phaseOf(session.status),
            sessionId = session.sessionId,
            mode = session.mode ?: resp.mode,
            requestedMode = session.requestedMode,
            adaptiveReason = session.adaptiveReason ?: resp.adaptiveReason,
            step = session.step,
            progress = session.progress,
            message = session.message.orEmpty(),
            updatedAt = session.updatedAt,
            publicUrl = session.url,
            urlUnavailableReason = session.urlUnavailableReason,
            materialsWarning = resp.materialsWarning,
            requestSourceNote = resp.requestSourceNote,
            errorCode = session.errorCode,
            retryable = session.retryable,
            partial = session.partial,
            error = session.error.orEmpty(),
        )
    }

    fun fromSession(
        session: InteractiveClassroomSessionDto,
        previous: ClassroomProgressState = ClassroomProgressState(),
    ): ClassroomProgressState {
        val next = phaseOf(session.status)
        return previous.copy(
            // 阶段只前进不回退：后端在终态后可能返回旧快照
            phase = if (previous.phase == ClassroomPhase.SUCCEEDED) previous.phase else next,
            sessionId = session.sessionId,
            mode = session.mode ?: previous.mode,
            requestedMode = session.requestedMode ?: previous.requestedMode,
            adaptiveReason = session.adaptiveReason ?: previous.adaptiveReason,
            step = session.step,
            progress = session.progress,
            message = session.message ?: previous.message,
            updatedAt = session.updatedAt ?: previous.updatedAt,
            publicUrl = session.url ?: previous.publicUrl,
            urlUnavailableReason = session.urlUnavailableReason ?: previous.urlUnavailableReason,
            errorCode = session.errorCode,
            retryable = session.retryable,
            partial = session.partial,
            error = session.error.orEmpty(),
        )
    }

    fun requesting(previous: ClassroomProgressState): ClassroomProgressState =
        ClassroomProgressState(phase = ClassroomPhase.REQUESTING, mode = previous.mode)

    fun failed(previous: ClassroomProgressState, message: String): ClassroomProgressState =
        previous.copy(phase = ClassroomPhase.FAILED, error = message)

    fun phaseOf(status: String?): ClassroomPhase = when (status?.trim()?.lowercase()) {
        "queued" -> ClassroomPhase.QUEUED
        "running" -> ClassroomPhase.RUNNING
        "succeeded" -> ClassroomPhase.SUCCEEDED
        "failed" -> ClassroomPhase.FAILED
        else -> ClassroomPhase.QUEUED
    }

    /** step 文案（对齐 OpenMAIC 真实步骤，未知阶段显示"处理中"）。 */
    fun stepLabel(step: String?): String = when (step) {
        "queued" -> "排队中"
        "initializing" -> "初始化课堂"
        "researching" -> "检索课程资料"
        "generating_outlines" -> "生成教学大纲"
        "generating_scenes" -> "生成课堂场景"
        "generating_media" -> "生成图片与视频"
        "generating_tts" -> "生成语音讲解"
        "persisting" -> "保存课堂"
        "completed" -> "已完成"
        "failed" -> "生成失败"
        else -> "处理中"
    }
}
