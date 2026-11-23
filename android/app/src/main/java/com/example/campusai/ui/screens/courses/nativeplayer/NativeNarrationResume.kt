package com.example.campusai.ui.screens.courses.nativeplayer

/** 退后台恢复讲解时，需要继续哪一段已有任务。 */
internal enum class NarrationResumeAction {
    None,
    Query,
    Poll,
    Download,
}

internal fun NativeNarrationUiState.awaitingAudio(): Boolean = loading || generating ||
    jobStatus == "queued" || jobStatus == "running" ||
    (jobStatus == "completed" && artifactId != null && audioFile == null && error == null)

/**
 * 恢复时优先复用已有结果：已缓存音频直接可用；已生成 artifact 只补下载；
 * 仍在排队/生成的任务继续轮询；其余情况重新查询服务端状态。
 */
internal fun narrationResumeAction(state: NativeNarrationUiState, sceneId: String): NarrationResumeAction {
    if (state.sceneId != sceneId) return NarrationResumeAction.Query
    if (state.audioFile != null) return NarrationResumeAction.None
    if (state.artifactId != null) return NarrationResumeAction.Download
    if (state.jobId != null && state.jobStatus in setOf("queued", "running")) {
        return NarrationResumeAction.Poll
    }
    return NarrationResumeAction.Query
}
