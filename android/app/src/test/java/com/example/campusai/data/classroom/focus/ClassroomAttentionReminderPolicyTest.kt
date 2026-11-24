package com.example.campusai.data.classroom.focus

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomAttentionReminderPolicyTest {
    private fun prediction(probability: Double = 0.9): ClassroomAttentionPrediction =
        ClassroomAttentionPrediction(
            probability = probability,
            logit = 2.0,
            threshold = 0.5,
            offTask = probability >= 0.5,
            missingFeatureCount = 0,
            modelVersion = "test-model",
        )

    private fun window(index: Int, stage: String = "slide"): ClassroomObservationWindow =
        ClassroomObservationWindow(
            index = index,
            startOffsetMs = index * 10_000L,
            endOffsetMs = (index + 1) * 10_000L,
            complete = true,
            validSampleCount = 40,
            invalidSampleCount = 0,
            faceVisibleSampleCount = 38,
            faceVisibleRatio = 0.95,
            yaw = ClassroomAxisStats(20.0, 4.0, 0.0, 30.0, 38),
            pitch = ClassroomAxisStats(-2.0, 4.0, -10.0, 8.0, 38),
            stageCounts = mapOf(stage to 40),
            dominantStage = stage,
            manualPageTurns = 0,
            quizSubmissions = 0,
            questions = 0,
            reasonCounts = emptyMap(),
            verdict = ClassroomObservationVerdict.OBSERVABLE,
            unavailableReason = null,
        )

    @Test
    fun `one off-task window is not enough evidence`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        assertNull(state.reminder)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(0.2), window(1))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(2))
        assertNull(state.reminder)
    }

    @Test
    fun `two consecutive off-task windows produce one gentle reminder`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1))
        assertEquals(1, state.reminder?.windowIndex)
        assertEquals(10_000L, state.reminder?.startOffsetMs)
        assertEquals(20_000L, state.reminder?.endOffsetMs)
    }

    @Test
    fun `duplicate and partial windows do not count and gaps start a new run`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1).copy(complete = false))
        assertNull(state.reminder)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(2))
        assertNull(state.reminder)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(3))
        assertEquals(3, state.reminder?.windowIndex)
    }

    @Test
    fun `lecture and quiz stages suppress reminders`() {
        for (stage in listOf("lecture", "quiz")) {
            var state = ClassroomAttentionReminderPolicy.setEnabled(
                ClassroomAttentionReminderPolicy.initial(),
                true,
            )
            state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0, stage))
            state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1, stage))
            assertNull("stage=$stage", state.reminder)
        }
    }

    @Test
    fun `cooldown blocks a second reminder for two minutes`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1))
        assertEquals(20_000L, state.lastAlertEndOffsetMs)
        state = ClassroomAttentionReminderPolicy.dismiss(state)
        for (index in 2..12) {
            state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(index))
        }
        assertNull(state.reminder)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(13))
        assertEquals(13, state.reminder?.windowIndex)
    }

    @Test
    fun `evidence without a gate resets the candidate run`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, null, window(1))
        assertEquals(0, state.consecutiveWindows)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(2))
        assertNull(state.reminder)
    }

    @Test
    fun `existing reminder stays until the student acts`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(0.2), window(2))
        assertTrue(state.reminder != null)
        state = ClassroomAttentionReminderPolicy.dismiss(state)
        assertNull(state.reminder)
    }

    @Test
    fun `note-taking feedback snoozes for five minutes`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1))
        state = ClassroomAttentionReminderPolicy.noteTaking(state, 20_000L)
        assertEquals(1, state.noteTakingCount)
        state = ClassroomAttentionReminderPolicy.dismiss(state)
        for (index in 2..31) {
            state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(index))
        }
        assertEquals("still snoozed until 320000", null, state.reminder)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(32))
        assertEquals(32, state.reminder?.windowIndex)
    }

    @Test
    fun `false-positive feedback snoozes for ten minutes and counts locally`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1))
        state = ClassroomAttentionReminderPolicy.falsePositive(state, 20_000L)
        assertEquals(1, state.falsePositiveCount)
        state = ClassroomAttentionReminderPolicy.dismiss(state)
        for (index in 2..61) {
            state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(index))
        }
        assertNull(state.reminder)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(62))
        assertEquals(62, state.reminder?.windowIndex)
    }

    @Test
    fun `pause blocks reminders until resumed`() {
        var state = ClassroomAttentionReminderPolicy.setEnabled(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.pause(state)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1))
        assertNull(state.reminder)
        assertTrue(state.paused)
        state = ClassroomAttentionReminderPolicy.resume(state)
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(2))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(3))
        assertEquals(3, state.reminder?.windowIndex)
    }

    @Test
    fun `disabled state never processes windows`() {
        val state = ClassroomAttentionReminderPolicy.onWindow(
            ClassroomAttentionReminderPolicy.initial(),
            prediction(),
            window(0),
        )
        assertNull(state.reminder)
        assertEquals(0, state.consecutiveWindows)
        assertFalse(state.processing)
    }

    @Test
    fun `debug preview is explicitly separate from the student switch`() {
        var state = ClassroomAttentionReminderPolicy.setPreview(
            ClassroomAttentionReminderPolicy.initial(),
            true,
        )
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(0))
        state = ClassroomAttentionReminderPolicy.onWindow(state, prediction(), window(1))
        assertTrue(state.preview)
        assertFalse(state.enabled)
        assertEquals(1, state.reminder?.windowIndex)
    }
}
