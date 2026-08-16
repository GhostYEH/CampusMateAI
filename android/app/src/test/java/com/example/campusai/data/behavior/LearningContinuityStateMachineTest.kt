package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Test

class LearningContinuityStateMachineTest {
    private val visible = BehaviorDisplayState.Stable(StudyBehavior.VISIBLE_STUDY, 0.9f)
    private val idle = BehaviorDisplayState.Stable(StudyBehavior.IDLE, 0.9f)

    @Test
    fun visibleStudyImmediatelyStartsStudying() {
        val machine = LearningContinuityStateMachine()
        assertEquals(LearningContinuityState.STUDYING, machine.process(visible, 1_000L).state)
    }

    @Test
    fun idleForFiveSecondsStaysStudying() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        assertEquals(LearningContinuityState.STUDYING, machine.process(idle, 7_000L).state)
    }

    @Test
    fun idleForTenSecondsBecomesThinkingOrAdjusting() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        assertEquals(LearningContinuityState.THINKING_OR_ADJUSTING, machine.process(idle, 12_000L).state)
    }

    @Test
    fun idleForTwentySecondsBecomesPaused() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        assertEquals(LearningContinuityState.PAUSED, machine.process(idle, 22_000L).state)
    }

    @Test
    fun visibleRecoveryFromThinkingKeepsTheOriginalStudyContext() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        machine.process(idle, 12_000L)
        val recovered = machine.process(visible, 15_000L)

        assertEquals(LearningContinuityState.STUDYING, recovered.state)
        assertEquals(1_000L, recovered.continuousStudyStartedAtMs)
    }

    @Test
    fun unknownDoesNotBreakStudying() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        assertEquals(LearningContinuityState.STUDYING, machine.process(BehaviorDisplayState.NoStableBehavior, 4_000L).state)
    }

    @Test
    fun historyCountsOnlyPausedAsAMeaningfulBreak() {
        val history = BehaviorObservationHistory()
        history.reset(1_000L)
        history.record(LearningContinuityState.STUDYING, 2_000L)
        history.record(LearningContinuityState.THINKING_OR_ADJUSTING, 12_000L)
        history.record(LearningContinuityState.STUDYING, 15_000L)
        history.record(LearningContinuityState.PAUSED, 25_000L)
        val summary = history.snapshot().summary(30_000L)

        assertEquals(23_000L, summary.longestContinuousStudyMs)
        assertEquals(1, summary.meaningfulSwitchCount)
    }

    @Test
    fun historyClipsTheRhythmToFiveMinutes() {
        val history = BehaviorObservationHistory()
        history.reset(1L)
        history.record(LearningContinuityState.STUDYING, 1_000L)
        history.record(LearningContinuityState.PAUSED, 121_000L)
        val summary = history.snapshot().summary(421_000L)

        assertEquals(0L, summary.recentStudyMs)
        assertEquals(300_000L, summary.recentPausedMs)
        assertEquals(120_000L, summary.totalStudyMs)
    }

    @Test
    fun newFocusSessionResetClearsHistory() {
        val history = BehaviorObservationHistory()
        history.reset(1_000L)
        history.record(LearningContinuityState.STUDYING, 2_000L)
        history.reset(10_000L)
        val summary = history.snapshot().summary(20_000L)

        assertEquals(0L, summary.totalStudyMs)
        assertEquals(0, summary.meaningfulSwitchCount)
    }
}
