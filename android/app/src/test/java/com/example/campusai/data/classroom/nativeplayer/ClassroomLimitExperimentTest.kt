package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.ClassroomPlaybackSceneDto
import kotlin.math.abs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomLimitExperimentTest {
    @Test
    fun cachedPlaybackRetainsSandboxAndProvidesNativeExperimentData() {
        val target = "#slider-eps"
        val dto = ClassroomPlaybackDto(scenes = listOf(ClassroomPlaybackSceneDto(
            id = "experiment",
            type = "interactive",
            content = mapOf("widgetType" to "simulation", "widgetConfig" to config, "html" to "<div>实验</div>"),
            render = mapOf("kind" to "sandbox-html", "sandbox" to "allow-scripts", "widget_type" to "simulation"),
            actions = listOf(mapOf("type" to "widget_highlight", "supported" to true, "payload" to mapOf("target" to target))),
        )))

        val document = NativeClassroomParser.parsePlayback(dto)
        val scenePlan = NativeClassroomParser.parsePlaybackPlan(dto).scenes.single()
        val experiment = document.interactiveByScene["experiment"]?.limitExperiment
        assertNotNull(experiment)
        assertEquals(NativeRenderKind.SANDBOX_HTML, scenePlan.renderKind)
        assertEquals("quadratic", experiment?.initialPresetId)
        assertEquals(ClassroomLimitExperiment.Highlight.EPSILON,
            ClassroomLimitExperiment.Highlight.fromSelector(document.scenes.single().actions.single().widgetTarget))
        assertEquals(NativeSceneMode.NATIVE, render(scenePlan.renderKind, experiment != null))
        assertEquals(NativeSceneMode.SANDBOX_HTML, render(scenePlan.renderKind, false))
        assertEquals(NativeSceneMode.UNAVAILABLE, render(NativeRenderKind.UNSUPPORTED, true))
        assertEquals(NativeSceneMode.SANDBOX_URL, render(NativeRenderKind.SANDBOX_URL, true))
    }

    @Test
    fun computesDeltaForEveryPresetAndKeepsSamplesInsideEpsilon() {
        val experiment = requireNotNull(ClassroomLimitExperiment.fromWidgetConfig(config))
        val expected = mapOf("linear" to 0.5, "quadratic" to 0.449489743, "sqrt" to 3.0)
        for (preset in experiment.presets) {
            assertEquals(expected.getValue(preset.id), preset.delta(1.0), 1e-8)
            for (epsilon in listOf(0.1, 0.3, 1.0, 2.0, 3.0)) {
                val radius = preset.delta(epsilon)
                for (sample in -9..9) {
                    val x = preset.center + radius * sample / 10.0
                    assertTrue(abs(preset.function.evaluate(x) - preset.limit) < epsilon)
                }
            }
        }
    }

    @Test
    fun rejectsUnrecognizedFormulaOrInvalidBoundsWithoutGuessingFromHtml() {
        val linear = presets.first()
        assertNull(ClassroomLimitExperiment.fromWidgetConfig(config + ("presets" to listOf(linear + ("name" to "线性 f(x) = x")))))
        assertNull(ClassroomLimitExperiment.fromWidgetConfig(config + ("presets" to listOf(linear + ("xMax" to Double.NaN)))))
        assertNull(ClassroomLimitExperiment.fromWidgetConfig(config + ("presets" to listOf(linear + ("L" to 8)))))
        assertNull(ClassroomLimitExperiment.fromWidgetConfig(config + ("initial" to mapOf("presetId" to "quadratic"))))
    }

    @Test
    fun everyApproachKeepsItsDomainAndConvergesToItsLimit() {
        val experiment = requireNotNull(ClassroomLimitExperiment.fromWidgetConfig(config))
        for (preset in experiment.presets) {
            val first = preset.approachX(0f)
            assertEquals(preset.center + ClassroomLimitExperiment.approachAmplitude, first, 1e-9)
            val last = preset.approachX(ClassroomLimitExperiment.durationSeconds)
            assertTrue(abs(last - preset.center) < 0.005)
            assertTrue(abs(preset.function.evaluate(last) - preset.limit) < 0.015)
        }
        val nearRootBoundary = experiment.presets.last().copy(center = 0.1)
        assertEquals(0.0, nearRootBoundary.approachX(.75f), 1e-9)
    }

    @Test
    fun orbitKeepsTheCameraAboveThePlotAndProjectsTimeInDepth() {
        val start = ClassroomLimitExperiment.ViewAngle()
        assertEquals(346f, start.orbit(-50f, -100f).yaw, 0f)
        assertEquals(8f, start.orbit(0f, -100f).pitch, 0f)
        assertEquals(70f, start.orbit(0f, 100f).pitch, 0f)
        val projection = LimitTrajectoryProjection(start)
        val near = LimitTrajectoryPoint(.5f, .5f, 0f)
        val far = near.copy(time = 1f)
        assertTrue(abs(projection.project(near).x - projection.project(far).x) > .5f)
        val opposite = LimitTrajectoryProjection(start.orbit(180f, 0f))
        assertTrue(opposite.project(near).x < opposite.project(far).x)
        for (yaw in 0..360 step 30) for (pitch in listOf(8f, 24f, 70f)) {
            val rotated = LimitTrajectoryProjection(ClassroomLimitExperiment.ViewAngle(yaw.toFloat(), pitch))
            for (x in listOf(0f, 1f)) for (y in listOf(0f, 1f)) for (time in listOf(0f, 1f)) {
                val corner = rotated.project(LimitTrajectoryPoint(x, y, time))
                assertTrue(corner.x.isFinite() && corner.y.isFinite())
            }
        }
    }

    private fun render(kind: NativeRenderKind, hasExperiment: Boolean) = NativePlaybackPolicy.decide(
        renderKind = kind,
        sceneType = "interactive",
        hasDocument = true,
        hasRenderableContent = true,
        fallbackAvailable = false,
        hasNativeExperiment = hasExperiment,
    ).mode

    private val presets = listOf(
        mapOf("id" to "linear", "name" to "线性函数 f(x) = 2x", "c" to 3, "L" to 6,
            "xMin" to 1, "xMax" to 5, "yMin" to 2, "yMax" to 10),
        mapOf("id" to "quadratic", "name" to "二次函数 f(x) = x²/2", "c" to 2, "L" to 2,
            "xMin" to 0, "xMax" to 4, "yMin" to 0, "yMax" to 8),
        mapOf("id" to "sqrt", "name" to "根式函数 f(x) = √x", "c" to 4, "L" to 2,
            "xMin" to 1, "xMax" to 7, "yMin" to 0, "yMax" to 4),
    )
    private val config = mapOf(
        "type" to "simulation",
        "presets" to presets,
        "initial" to mapOf("presetId" to "quadratic", "epsilon" to 1.0, "speed" to 1.0),
    )
}
