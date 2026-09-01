package com.example.campusai.ui.screens.tasks

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskImportDraftModelTest {
    private val duplicate = TaskImportDraftState(
        title = "课程报告",
        selected = false,
        existingTaskId = "task-1",
        existingStatus = "pending",
        detectedTitle = "课程报告",
    )

    @Test
    fun `editing duplicate title only by whitespace or case keeps existing metadata`() {
        val edited = updateImportDraftTitle(duplicate, "  课程报告  ")

        assertEquals("task-1", edited.existingTaskId)
        assertEquals("pending", edited.existingStatus)
        assertTrue(!edited.selected)
    }

    @Test
    fun `case and repeated whitespace do not turn a duplicate into a new task`() {
        val englishDuplicate = duplicate.copy(title = "Read Chapter", detectedTitle = "Read Chapter")

        val edited = updateImportDraftTitle(englishDuplicate, "  READ   CHAPTER  ")

        assertEquals("task-1", edited.existingTaskId)
        assertTrue(!edited.selected)
    }

    @Test
    fun `renaming duplicate title clears existing metadata and selects it`() {
        val edited = updateImportDraftTitle(duplicate, "课程报告终稿")

        assertNull(edited.existingTaskId)
        assertNull(edited.existingStatus)
        assertTrue(edited.selected)
    }

    @Test
    fun `renaming a duplicate back restores existing metadata and deselects it`() {
        val renamed = updateImportDraftTitle(duplicate, "课程报告终稿")

        val restored = updateImportDraftTitle(renamed, "课程报告")

        assertEquals("task-1", restored.existingTaskId)
        assertEquals("pending", restored.existingStatus)
        assertTrue(!restored.selected)
    }

    @Test
    fun `commit request preserves analyzed task metadata`() {
        val draft = TaskImportDraftState(
            title = "提交课程报告",
            description = "完成第三章",
            materials = listOf("报告 PDF", "数据附件"),
            submissionMethod = "学习平台",
            location = "线上",
            importance = "high",
        )

        val request = draft.toImportCreateRequest()

        assertEquals(listOf("报告 PDF", "数据附件"), request.materials)
        assertEquals("学习平台", request.submission_method)
        assertEquals("线上", request.location)
        assertEquals("high", request.importance)
    }
}
