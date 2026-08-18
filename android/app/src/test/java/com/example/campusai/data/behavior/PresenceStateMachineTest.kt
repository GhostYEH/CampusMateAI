package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PresenceStateMachineTest {
    private fun machine() = PresenceStateMachine(
        PresenceConfig(personHoldMs = 2_000L, presenceGraceMs = 12_000L),
    )

    @Test
    fun personEvidenceImmediatelySetsPresent() {
        assertEquals(PresenceState.PRESENT, machine().process(1_000L, true, false, false).state)
    }

    @Test
    fun personBrieflyMissingWithinHoldStaysPresent() {
        val machine = machine()
        machine.process(1_000L, true, false, false)
        val result = machine.process(2_999L, false, false, false)

        assertEquals(PresenceState.PRESENT, result.state)
        assertTrue(result.recentPersonEvidence)
    }

    @Test
    fun visibleStudyEvidenceIsPresentWithoutPerson() {
        assertEquals(PresenceState.PRESENT, machine().process(1_000L, false, false, true).state)
    }

    @Test
    fun faceEvidenceIsPresentWithoutPerson() {
        assertEquals(PresenceState.PRESENT, machine().process(1_000L, false, true, false).state)
    }

    @Test
    fun observingIsOnlyUsedBeforeAnyEvidence() {
        assertEquals(PresenceState.OBSERVING, machine().process(1_000L, false, false, false).state)
    }

    @Test
    fun missingAllEvidenceForLessThanGraceIsNotAbsent() {
        val machine = machine()
        machine.process(1_000L, true, false, false)
        assertEquals(PresenceState.PRESENT, machine.process(12_999L, false, false, false).state)
    }

    @Test
    fun missingAllEvidenceForGracePeriodIsAbsent() {
        val machine = machine()
        machine.process(1_000L, true, false, false)
        assertEquals(PresenceState.ABSENT, machine.process(13_000L, false, false, false).state)
    }

    @Test
    fun personRecoveryImmediatelyRestoresPresent() {
        val machine = machine()
        machine.process(1_000L, true, false, false)
        machine.process(13_000L, false, false, false)
        assertEquals(PresenceState.PRESENT, machine.process(13_100L, true, false, false).state)
    }

    @Test
    fun persistentPersonEvidenceKeepsPresentWhenFaceIsMissing() {
        val machine = machine()
        assertEquals(PresenceState.PRESENT, machine.process(1_000L, true, false, false).state)
        assertEquals(PresenceState.PRESENT, machine.process(5_000L, true, false, false).state)
        assertEquals(PresenceState.PRESENT, machine.process(9_000L, true, false, false).state)
    }
}
