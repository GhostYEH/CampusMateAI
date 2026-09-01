package com.example.campusai.ui.screens.tasks

import com.example.campusai.data.remote.PersonalTaskCreateRequest

/** UI-only import state. [detectedTitle] preserves the server's duplicate comparison title. */
data class TaskImportDraftState(
    val title: String,
    val description: String = "",
    val deadline: String? = null,
    val sourceName: String? = null,
    val sourceText: String? = null,
    val priority: String = "medium",
    val materials: List<String> = emptyList(),
    val submissionMethod: String? = null,
    val location: String? = null,
    val importance: String = "unknown",
    val needsConfirmation: Boolean = false,
    val warnings: List<String> = emptyList(),
    val selected: Boolean = true,
    val existingTaskId: String? = null,
    val existingStatus: String? = null,
    val detectedTitle: String = title,
    val detectedExistingTaskId: String? = existingTaskId,
    val detectedExistingStatus: String? = existingStatus,
)

fun TaskImportDraftState.toImportCreateRequest(): PersonalTaskCreateRequest =
    PersonalTaskCreateRequest(
        title = title.trim(),
        description = description.ifBlank { null },
        deadline = deadline,
        source_name = sourceName,
        source_text = sourceText,
        priority = priority,
        materials = materials,
        submission_method = submissionMethod,
        location = location,
        importance = importance,
    )

fun normalizeImportDraftTitle(title: String): String =
    title.trim().lowercase().split(Regex("\\s+")).joinToString(" ")

fun updateImportDraftTitle(draft: TaskImportDraftState, title: String): TaskImportDraftState {
    val matchesDetectedTitle =
        normalizeImportDraftTitle(title) == normalizeImportDraftTitle(draft.detectedTitle)
    return when {
        draft.detectedExistingTaskId != null && matchesDetectedTitle -> draft.copy(
            title = title,
            selected = false,
            existingTaskId = draft.detectedExistingTaskId,
            existingStatus = draft.detectedExistingStatus,
        )
        draft.detectedExistingTaskId != null -> draft.copy(
            title = title,
            selected = true,
            existingTaskId = null,
            existingStatus = null,
        )
        else -> draft.copy(title = title)
    }
}
