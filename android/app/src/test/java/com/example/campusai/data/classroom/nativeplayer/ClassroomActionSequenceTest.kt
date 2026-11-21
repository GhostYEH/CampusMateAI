package com.example.campusai.data.classroom.nativeplayer

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ClassroomActionSequenceTest {

    @Test
    fun `planner keeps server steps order even when actions are listed differently`() {
        val actions = listOf(
            action("a1", "speech"),
            action("a2", "play_video"),
        )
        val plan = ClassroomActionSequencePlanner.plan(
            sceneId = "scene-1",
            steps = listOf(
                NativePlaybackStep("a2", "play_video", "sync"),
                NativePlaybackStep("a1", "speech", "sync"),
            ),
            actions = actions,
        )

        assertEquals("scene-1", plan.sceneId)
        assertEquals(listOf("a2", "a1"), plan.steps.map { it.actionId })
        assertEquals("a2", plan.steps[0].action?.id)
        assertEquals("a1", plan.steps[1].action?.id)
        assertTrue(plan.steps.all { it.problem == null })
    }

    @Test
    fun `planner reports missing and unsupported actions without waiting semantics`() {
        val plan = ClassroomActionSequencePlanner.plan(
            sceneId = "scene-2",
            steps = listOf(
                NativePlaybackStep("missing", "speech", "sync"),
                NativePlaybackStep("unsupported", "widget_boom", "sync"),
                NativePlaybackStep("spot", "spotlight", "sync"),
            ),
            actions = listOf(
                action("unsupported", "widget_boom", supported = false, reason = "widget_runtime_missing"),
                action("spot", "spotlight"),
            ),
        )

        assertEquals("missing", plan.steps[0].actionId)
        assertNull(plan.steps[0].action)
        assertTrue(plan.steps[0].problem?.contains("没有对应的课堂动作") == true)
        assertEquals("widget_runtime_missing", plan.steps[1].problem)
        assertEquals("fire_and_forget", plan.steps[2].mode)
        assertFalse(plan.steps[2].blocking)
    }

    @Test
    fun `runner waits for the current step completion before starting the next`() = runTest {
        val events = mutableListOf<String>()
        val firstStarted = CompletableDeferred<Unit>()
        val releaseFirst = CompletableDeferred<Unit>()
        var result: ClassroomSequenceResult? = null
        val job = launch {
            result = runClassroomSequence(
                steps = steps("a1", "a2"),
                isCurrent = { true },
                awaitPause = {},
                onStep = { _, step -> events += "start:${step.actionId}" },
                execute = { step, _ ->
                    if (step.actionId == "a1") {
                        firstStarted.complete(Unit)
                        releaseFirst.await()
                    }
                    events += "done:${step.actionId}"
                    ClassroomSequenceStepResult.Completed
                },
            )
        }
        firstStarted.await()
        assertEquals(listOf("start:a1"), events)
        releaseFirst.complete(Unit)
        job.join()
        assertEquals(listOf("start:a1", "done:a1", "start:a2", "done:a2"), events)
        assertTrue(result is ClassroomSequenceResult.Completed)
    }

    @Test
    fun `late completion after scene switch cannot start the next page action`() = runTest {
        val events = mutableListOf<String>()
        val firstStarted = CompletableDeferred<Unit>()
        val releaseFirst = CompletableDeferred<Unit>()
        var scene = "scene-a"
        var result: ClassroomSequenceResult? = null
        val job = launch {
            result = runClassroomSequence(
                steps = steps("a1", "a2"),
                isCurrent = { scene == "scene-a" },
                awaitPause = {},
                onStep = { _, step -> events += "start:${step.actionId}" },
                execute = { step, _ ->
                    if (step.actionId == "a1") {
                        firstStarted.complete(Unit)
                        releaseFirst.await()
                    }
                    events += "done:${step.actionId}"
                    ClassroomSequenceStepResult.Completed
                },
            )
        }
        firstStarted.await()
        scene = "scene-b"
        releaseFirst.complete(Unit)
        job.join()

        assertEquals(listOf("start:a1", "done:a1"), events)
        assertEquals(ClassroomSequenceResult.Cancelled, result)
    }

    @Test
    fun `pause gate prevents the next action from starting until resumed`() = runTest {
        val events = mutableListOf<String>()
        var paused = true
        val job = launch {
            runClassroomSequence(
                steps = steps("a1"),
                isCurrent = { true },
                awaitPause = { while (paused) delay(50L) },
                onStep = { _, step -> events += step.actionId },
                execute = { _, _ -> ClassroomSequenceStepResult.Completed },
            )
        }
        runCurrent()
        assertTrue(events.isEmpty())
        paused = false
        advanceUntilIdle()
        job.join()
        assertEquals(listOf("a1"), events)
    }

    @Test
    fun `failed media stops the sequence and does not run later steps`() = runTest {
        val events = mutableListOf<String>()
        var result: ClassroomSequenceResult? = null
        val job = launch {
            result = runClassroomSequence(
                steps = steps("a1", "a2"),
                isCurrent = { true },
                awaitPause = {},
                onStep = { _, step -> events += "start:${step.actionId}" },
                execute = { step, _ ->
                    if (step.actionId == "a1") {
                        ClassroomSequenceStepResult.Failed("audio 404")
                    } else {
                        events += "start:${step.actionId}"
                        ClassroomSequenceStepResult.Completed
                    }
                },
            )
        }
        job.join()
        assertEquals(listOf("start:a1"), events)
        assertTrue(result is ClassroomSequenceResult.Failed)
        assertEquals("audio 404", (result as ClassroomSequenceResult.Failed).reason)
    }

    private fun steps(vararg ids: String): List<ClassroomSequenceStep> = ids.mapIndexed { index, id ->
        ClassroomSequenceStep(
            index = index,
            actionId = id,
            type = "speech",
            mode = "sync",
            action = action(id, "speech"),
        )
    }

    private fun action(
        id: String,
        type: String,
        supported: Boolean = true,
        reason: String? = null,
    ) = NativeAction(
        id = id,
        type = type,
        title = id,
        supported = supported,
        reason = reason,
    )
}
