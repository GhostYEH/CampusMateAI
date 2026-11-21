package com.example.campusai.data.focus

import com.example.campusai.data.behavior.BehaviorDisplayState
import com.example.campusai.data.behavior.PresenceState
import com.example.campusai.data.behavior.StudyBehavior
import org.junit.Assert.assertEquals
import org.junit.Test

class ClassroomAttentionTrackerTest {
    private fun stable(behavior: StudyBehavior) = BehaviorDisplayState.Stable(behavior, 0.9f)

    @Test
    fun focusAndDistractionNeedStableEvidence() {
        val tracker = ClassroomAttentionTracker()
        assertEquals(ClassroomAttentionState.UNKNOWN, tracker.process(null, PresenceState.OBSERVING, FocusState.UNAVAILABLE, 0L).state)
        assertEquals(ClassroomAttentionState.UNKNOWN, tracker.process(stable(StudyBehavior.READING), PresenceState.PRESENT, FocusState.FOCUSED, 1_000L).state)
        assertEquals(ClassroomAttentionState.FOCUSED, tracker.process(stable(StudyBehavior.READING), PresenceState.PRESENT, FocusState.FOCUSED, 6_000L).state)
        assertEquals(ClassroomAttentionState.FOCUSED, tracker.process(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 7_000L).state)
        assertEquals(ClassroomAttentionState.DISTRACTED, tracker.process(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 12_000L).state)
    }

    @Test
    fun absenceWinsOverOtherSignals() {
        val tracker = ClassroomAttentionTracker()
        assertEquals(ClassroomAttentionState.AWAY, tracker.process(stable(StudyBehavior.READING), PresenceState.ABSENT, FocusState.NO_FACE, 1_000L).state)
    }

    @Test
    fun idleIsPossiblyDistractedButDrowsinessIsDistracted() {
        val tracker = ClassroomAttentionTracker()
        assertEquals(ClassroomAttentionState.FOCUSED, tracker.process(stable(StudyBehavior.READING), PresenceState.PRESENT, FocusState.FOCUSED, 0L).state)
        assertEquals(ClassroomAttentionState.FOCUSED, tracker.process(stable(StudyBehavior.IDLE), PresenceState.PRESENT, FocusState.FOCUSED, 1_000L).state)
        assertEquals(ClassroomAttentionState.POSSIBLY_DISTRACTED, tracker.process(stable(StudyBehavior.IDLE), PresenceState.PRESENT, FocusState.FOCUSED, 6_000L).state)
        assertEquals(ClassroomAttentionState.POSSIBLY_DISTRACTED, tracker.process(stable(StudyBehavior.DROWSY), PresenceState.PRESENT, FocusState.FOCUSED, 7_000L).state)
        assertEquals(ClassroomAttentionState.DISTRACTED, tracker.process(stable(StudyBehavior.DROWSY), PresenceState.PRESENT, FocusState.FOCUSED, 12_000L).state)
    }

    @Test
    fun resetStartsWithUnknown() {
        val tracker = ClassroomAttentionTracker()
        tracker.process(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 1_000L)
        tracker.reset()
        assertEquals(ClassroomAttentionState.UNKNOWN, tracker.process(null, PresenceState.OBSERVING, FocusState.UNAVAILABLE, 2_000L).state)
    }
}
