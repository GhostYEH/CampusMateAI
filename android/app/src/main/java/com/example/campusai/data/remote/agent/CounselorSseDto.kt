package com.example.campusai.data.remote.agent

import com.squareup.moshi.Json
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

/**
 * Stable, credential-free metadata carried by the counselor `done` SSE event.
 * The answer itself is still rendered from streamed chunks; this DTO only keeps
 * the final conversation metadata and typed actions needed by the UI.
 */
data class CounselorFinalMetaDto(
    val answer: String = "",
    @Json(name = "conversation_id") val conversationId: String? = null,
    @Json(name = "suggested_actions") val suggestedActions: List<SuggestedActionDto> = emptyList(),
    val warnings: List<String> = emptyList(),
)

data class SuggestedActionDto(
    val id: String = "",
    val label: String = "",
    val type: String = "none",
    val payload: String? = null,
    val data: Map<String, Any?> = emptyMap(),
) {
    fun interactiveClassroomProposal(): InteractiveClassroomProposalDto? {
        if (type != "interactiveClassroomProposal") return null
        val courseId = data.stringValue("course_id") ?: return null
        return InteractiveClassroomProposalDto(
            proposalId = data.stringValue("proposal_id").orEmpty(),
            courseId = courseId,
            courseName = data.stringValue("course_name").orEmpty(),
            mode = data.stringValue("mode") ?: "adaptive",
            modeLabel = data.stringValue("mode_label").orEmpty(),
            intentNote = data.stringValue("intent_note").orEmpty(),
            available = data.booleanValue("available"),
            reason = data.stringValue("reason"),
            requiresConfirmation = data.booleanValue("requires_confirmation", default = true),
        )
    }
}

data class InteractiveClassroomProposalDto(
    /**
     * 服务端下发的**提案唯一身份**。
     *
     * `SuggestedAction.id` 是常量（同类提案共用），无法区分"同一门课的第二个提案"，
     * 客户端据此会把第二个提案误当成第一个 —— 复用旧 job、旧幂等键、旧深链。
     * 旧后端可能不下发该字段，此时退化为空串（见 ClassroomProposalScope）。
     */
    @Json(name = "proposal_id") val proposalId: String = "",
    @Json(name = "course_id") val courseId: String,
    @Json(name = "course_name") val courseName: String,
    val mode: String,
    @Json(name = "mode_label") val modeLabel: String,
    @Json(name = "intent_note") val intentNote: String,
    val available: Boolean,
    val reason: String? = null,
    @Json(name = "requires_confirmation") val requiresConfirmation: Boolean = true,
)

private fun Map<String, Any?>.stringValue(key: String): String? =
    this[key]?.toString()?.trim()?.takeIf { it.isNotEmpty() }

private fun Map<String, Any?>.booleanValue(key: String, default: Boolean = false): Boolean =
    when (val value = this[key]) {
        is Boolean -> value
        is String -> value.equals("true", ignoreCase = true)
        is Number -> value.toInt() != 0
        null -> default
        else -> default
    }

object CounselorSseParser {
    private val adapter = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()
        .adapter(CounselorFinalMetaDto::class.java)

    fun parseFinalMeta(json: String?): CounselorFinalMetaDto? =
        json?.takeIf { it.isNotBlank() }?.let { runCatching { adapter.fromJson(it) }.getOrNull() }
}
