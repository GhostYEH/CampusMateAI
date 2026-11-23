package com.example.campusai.data.classroom.focus

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomFocusObservationExportTest {
    private fun windows(): List<ClassroomObservationWindow> {
        var state = ClassroomFocusObservation.begin(0)
        repeat(40) { index ->
            state = ClassroomFocusObservation.applySample(
                state = state,
                atMs = index * 250L,
                faceCount = 1,
                yawDegrees = -4.0,
                pitchDegrees = -8.0,
                stage = "slide",
                sessionId = state.sessionId,
            )
        }
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 3_000,
        )
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.SUBMIT_ANSWER, 5_000,
        )
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.ASK_QUESTION, 7_000,
        )
        return ClassroomFocusObservation.windowsForExport(state, 10_000)
    }

    @Test
    fun `csv contains window facts and excludes raw media identity`() {
        val csv = ClassroomObservationExport.csv(windows())
        assertTrue(csv.startsWith("window_index,start_offset_ms,end_offset_ms,complete,"))
        assertTrue(csv.contains("observable"))
        assertTrue(csv.contains("slide:40"))
        assertTrue(csv.contains("manual_page_turns"))
        assertTrue(csv.contains("unavailable_reason_counts"))
        assertFalse(csv.contains("frame"))
        assertFalse(csv.contains("image"))
        assertFalse(csv.contains("title"))
        assertFalse(csv.contains("student_id"))
        assertFalse(csv.contains("http"))
    }

    @Test
    fun `json is window level and uses reason codes`() {
        val json = ClassroomObservationExport.json(windows())
        assertTrue(json.startsWith("{\"version\":1,\"windows\":["))
        assertTrue(json.contains("\"faceVisibleRatio\""))
        assertTrue(json.contains("\"stageCounts\":{\"slide\":40}"))
        assertTrue(json.contains("\"manualPageTurns\":1"))
        assertTrue(json.contains("\"quizSubmissions\":1"))
        assertTrue(json.contains("\"questions\":1"))
        assertTrue(json.contains("\"unavailableReasonCounts\":{}"))
        assertFalse(json.contains("frame"))
        assertFalse(json.contains("image"))
        assertFalse(json.contains("title"))
    }

    @Test
    fun `unobservable reason is encoded as stable code`() {
        var state = ClassroomFocusObservation.begin(0)
        repeat(40) { index ->
            state = ClassroomFocusObservation.noteInvalidSample(
                state = state,
                atMs = index * 250L,
                reason = ClassroomFocusReason.LOW_LIGHT,
                sessionId = state.sessionId,
            )
        }
        val csv = ClassroomObservationExport.csv(
            ClassroomFocusObservation.windowsForExport(state, 10_000),
        )
        assertTrue(csv.contains("low_light"))
        assertTrue(csv.contains("unobservable"))
    }
}
