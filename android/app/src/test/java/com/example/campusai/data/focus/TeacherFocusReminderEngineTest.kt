package com.example.campusai.data.focus

import com.example.campusai.data.behavior.BehaviorDisplayState
import com.example.campusai.data.behavior.PresenceState
import com.example.campusai.data.behavior.StudyBehavior
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TeacherFocusReminderEngineTest {
    private fun stable(behavior: StudyBehavior) = BehaviorDisplayState.Stable(behavior, 0.9f)

    @Test
    fun phoneReminderWaitsForSustainedEvidence() {
        val engine = TeacherFocusReminderEngine()
        assertNull(engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 0L))
        assertNull(engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 2_000L))
        val reminder = engine.observe(
            stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 4_200L,
        )
        assertNotNull(reminder)
        assertEquals(TeacherReminderKind.PHONE, reminder!!.kind)
        assertTrue(reminder.message.contains("手机"))
    }

    @Test
    fun sameKindRespectsKindCooldownButOtherKindCanFollowGlobalCooldown() {
        val engine = TeacherFocusReminderEngine()
        assertNull(engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 0L))
        val first = engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 5_000L)
        assertNotNull(first)
        assertNull(engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 60_000L))
        // A different kind must still wait for the global 45 s cooldown.
        assertNull(engine.observe(stable(StudyBehavior.IDLE), PresenceState.PRESENT, FocusState.FOCUSED, 80_000L))
        val second = engine.observe(stable(StudyBehavior.IDLE), PresenceState.PRESENT, FocusState.FOCUSED, 125_000L)
        assertNotNull(second)
        assertEquals(TeacherReminderKind.NO_STUDY, second!!.kind)
    }

    @Test
    fun absenceAndDrowsinessUseCareReminders() {
        val absentEngine = TeacherFocusReminderEngine()
        assertNull(absentEngine.observe(
            BehaviorDisplayState.NoStableBehavior, PresenceState.ABSENT, FocusState.NO_FACE, 0L,
        ))
        val absent = absentEngine.observe(
            BehaviorDisplayState.NoStableBehavior, PresenceState.ABSENT, FocusState.NO_FACE, 9_000L,
        )
        assertEquals(TeacherReminderKind.ABSENT, absent!!.kind)
        assertEquals(TeacherReminderTone.CARE, absent.tone)

        val drowsyEngine = TeacherFocusReminderEngine()
        assertNull(drowsyEngine.observe(stable(StudyBehavior.DROWSY), PresenceState.PRESENT, FocusState.FOCUSED, 0L))
        val drowsy = drowsyEngine.observe(
            stable(StudyBehavior.DROWSY), PresenceState.PRESENT, FocusState.FOCUSED, 9_000L,
        )
        assertEquals(TeacherReminderKind.DROWSY, drowsy!!.kind)
        assertEquals(TeacherReminderTone.CARE, drowsy.tone)
    }

    @Test
    fun recoveryPraiseNeedsSustainedStudy() {
        val engine = TeacherFocusReminderEngine()
        assertNull(engine.observe(stable(StudyBehavior.IDLE), PresenceState.PRESENT, FocusState.FOCUSED, 0L))
        assertNotNull(engine.observe(stable(StudyBehavior.IDLE), PresenceState.PRESENT, FocusState.FOCUSED, 20_000L))
        assertNull(engine.observe(stable(StudyBehavior.READING), PresenceState.PRESENT, FocusState.FOCUSED, 25_000L))
        val praise = engine.observe(stable(StudyBehavior.READING), PresenceState.PRESENT, FocusState.FOCUSED, 36_000L)
        assertEquals(TeacherReminderKind.RECOVERED, praise!!.kind)
        assertEquals(TeacherReminderTone.PRAISE, praise.tone)
    }

    @Test
    fun sessionReminderCountIsCapped() {
        val config = TeacherReminderConfig(
            phoneTriggerMs = 0,
            noStudyTriggerMs = 0,
            lookAwayTriggerMs = 0,
            drowsyTriggerMs = 0,
            absentTriggerMs = 0,
            globalCooldownMs = 0,
            kindCooldownMs = 0,
            maxPerSession = 2,
        )
        val engine = TeacherFocusReminderEngine(config)
        assertNotNull(engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 1_000L))
        assertNotNull(engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 2_000L))
        assertNull(engine.observe(stable(StudyBehavior.IDLE), PresenceState.PRESENT, FocusState.FOCUSED, 3_000L))
        engine.reset()
        assertNotNull(engine.observe(stable(StudyBehavior.PHONE_USE), PresenceState.PRESENT, FocusState.FOCUSED, 4_000L))
    }
}
