package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.ClassroomPlaybackSceneDto
import com.example.campusai.data.remote.MagicClassWorkspaceStageDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomParameterExperimentTest {
    private fun field(id: String, value: Double = 2.0, step: Double = .1) = mapOf(
        "id" to id, "label" to id, "unit" to "U", "min" to 0.0, "max" to 10.0, "step" to step, "value" to value,
    )

    private val config = mapOf(
        "type" to "simulation", "nativeRenderer" to "classroom-parameter-experiment/1",
        "description" to "改变参数，观察因变量。", "controls" to listOf(field("voltage", 6.0), field("resistance", 3.0)),
        "resultLabel" to "电流", "resultUnit" to "A", "expression" to listOf("voltage", "resistance", "/"),
        "chartParameter" to "voltage", "presets" to listOf(mapOf("label" to "9 V", "values" to mapOf("voltage" to 9.0))),
    )

    @Test
    fun sliderPresetsAndTeacherChangesDriveTheSameFormula() {
        val experiment = requireNotNull(ClassroomParameterExperiment.fromWidgetConfig(config))
        assertEquals(2.0, requireNotNull(experiment.calculate(experiment.initialValues)), 1e-10)
        val preset = experiment.presets.single()
        assertEquals(3.0, requireNotNull(experiment.calculate(experiment.initialValues + preset.values)), 1e-10)
        val changed = requireNotNull(experiment.validatedChanges(mapOf("voltage" to 7.37)))
        assertEquals(7.4, changed.getValue("voltage"), 1e-10)
        assertNull(experiment.calculate(experiment.initialValues + ("resistance" to 0.0)))
        assertNull(experiment.validatedChanges(mapOf("resistance" to -1.0)))
        assertTrue(experiment.supportsActions(listOf(NativeAction("set", "widget_setState", widgetState = changed))))
        assertFalse(experiment.supportsActions(listOf(NativeAction("set", "widget_setState", widgetState = mapOf("script" to 1.0)))))
        assertFalse(experiment.supportsActions(listOf(NativeAction("draw", "widget_reveal"))))
    }

    @Test
    fun validatesExpressionsAndSamplesForOtherSubjects() {
        val motion = config + mapOf(
            "controls" to listOf(field("time", 2.0)),
            "resultLabel" to "位移", "expression" to listOf("time", 2, "^", 4.9, "*"), "chartParameter" to "time",
            "presets" to emptyList<Any>(),
        )
        val experiment = requireNotNull(ClassroomParameterExperiment.fromWidgetConfig(motion))
        assertEquals(19.6, requireNotNull(experiment.calculate(experiment.initialValues)), 1e-10)
        val invalid = listOf(
            config - "nativeRenderer",
            config + ("expression" to listOf("voltage", "+")),
            config + ("expression" to listOf("voltage", "unknown", "*")),
            config + ("expression" to listOf("voltage", "voltage")),
            config + ("chartParameter" to "missing"),
            config + ("controls" to listOf(field("voltage", step = 3.0), field("resistance", 3.0))),
        )
        invalid.forEach { assertNull(ClassroomParameterExperiment.fromWidgetConfig(it)) }
    }

    @Test
    fun admitsTheSameDataInClassicAndManagedAndRetainsWidgetActions() {
        val sceneContent = mapOf(
            "type" to "interactive", "widgetType" to "simulation", "widgetConfig" to config,
            "html" to "<main>实验</main>",
        )
        val plan = ClassroomPlaybackSceneDto(
            id = "ordinary", title = "普通实验", type = "interactive", content = sceneContent,
            actions = listOf(mapOf("id" to "guide", "type" to "widget_setState", "payload" to mapOf("state" to mapOf("voltage" to 9.0)))),
        )
        val classic = NativeClassroomParser.parsePlayback(ClassroomPlaybackDto(scenes = listOf(plan)))
        val managed = NativeClassroomParser.parseStage(MagicClassWorkspaceStageDto(
            id = "managed", document = mapOf("scenes" to listOf(mapOf("id" to "ordinary", "type" to "interactive", "content" to sceneContent))),
        ))
        val classicWidget = requireNotNull(classic.interactiveByScene["ordinary"]?.parameterExperiment)
        val managedWidget = requireNotNull(managed.interactiveByScene["ordinary"]?.parameterExperiment)
        assertEquals(classicWidget.initialValues, managedWidget.initialValues)
        assertTrue(classicWidget.supportsActions(classic.scenes.single().actions))
        assertEquals(9.0, classic.scenes.single().actions.single().widgetState?.get("voltage"))
        assertEquals("<main>实验</main>", classic.interactiveByScene["ordinary"]?.html)
    }
}
