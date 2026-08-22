package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * V3.1.1 added `debugInferenceLatencyMs` / `debugPreprocessingLatencyMs` to
 * BehaviorPrediction. LearningContinuityStateMachine only consumes
 * BehaviorDisplayState (produced by BehaviorSignalProcessor), so it must be
 * unaffected by the V3.1.1 debug fields. These tests replay the canonical
 * continuity scenarios and assert the states still match the V3.1 contract.
 */
class LearningContinuityStateMachineV311RegressionTest {

    private val visible = BehaviorDisplayState.Stable(StudyBehavior.VISIBLE_STUDY, 0.9f)
    private val idle = BehaviorDisplayState.Stable(StudyBehavior.IDLE, 0.9f)

    @Test
    fun visibleStudyImmediatelyStartsStudying() {
        val machine = LearningContinuityStateMachine()
        assertEquals(LearningContinuityState.STUDYING, machine.process(visible, 1_000L).state)
    }

    @Test
    fun idleWithinGracePeriodStaysStudying() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        assertEquals(LearningContinuityState.STUDYING, machine.process(idle, 7_000L).state)
    }

    @Test
    fun idlePastGraceButBeforePausedBecomesThinkingOrAdjusting() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        assertEquals(
            LearningContinuityState.THINKING_OR_ADJUSTING,
            machine.process(idle, 12_000L).state,
        )
    }

    @Test
    fun idlePastPausedThresholdBecomesPaused() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        assertEquals(LearningContinuityState.PAUSED, machine.process(idle, 22_000L).state)
    }

    @Test
    fun visibleRecoveryFromThinkingPreservesOriginalStudyContext() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        machine.process(idle, 2_000L)
        machine.process(idle, 12_000L)
        val recovered = machine.process(visible, 15_000L)

        assertEquals(LearningContinuityState.STUDYING, recovered.state)
        assertEquals(1_000L, recovered.continuousStudyStartedAtMs)
    }

    @Test
    fun noStableBehaviorDoesNotBreakStudying() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        assertEquals(
            LearningContinuityState.STUDYING,
            machine.process(BehaviorDisplayState.NoStableBehavior, 4_000L).state,
        )
    }

    @Test
    fun observingDoesNotBreakStudying() {
        val machine = LearningContinuityStateMachine()
        machine.process(visible, 1_000L)
        assertEquals(
            LearningContinuityState.STUDYING,
            machine.process(BehaviorDisplayState.Observing, 4_000L).state,
        )
    }
}