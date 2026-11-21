package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.ClassroomPlaybackSceneDto
import com.example.campusai.data.remote.MagicClassWorkspaceStageDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomSpatialExperimentTest {
    private fun solid(id: String, type: String) = mapOf(
        "id" to id, "name" to id, "type" to type, "material" to mapOf("color" to "#DAB27A"),
    )

    private fun config(objects: List<Map<String, Any?>> = listOf(solid("cuboid", "box"))) = mapOf(
        "type" to "visualization3d", "nativeRenderer" to "classroom-spatial/1",
        "description" to "拖动观察空间关系", "objects" to objects,
        "interactions" to listOf(mapOf("type" to "orbit", "target" to "camera"), mapOf("type" to "zoom", "target" to "camera")),
    )

    private fun content(widget: Map<String, Any?>) = mapOf(
        "type" to "interactive", "widgetType" to "visualization3d", "html" to "<p>实验简介</p>", "widgetConfig" to widget,
    )

    @Test
    fun independentGeneratedModelsAreReadFromClassicAndManagedDocuments() {
        val classic = NativeClassroomParser.parsePlayback(ClassroomPlaybackDto(scenes = listOf(
            ClassroomPlaybackSceneDto(
                id = "surface", type = "interactive", title = "圆锥的侧面",
                content = content(config(listOf(solid("cone_a", "cone")))),
            ),
        )))
        val managed = NativeClassroomParser.parseStage(MagicClassWorkspaceStageDto(
            id = "new-stage",
            document = mapOf("scenes" to listOf(mapOf(
                "id" to "planet", "type" to "interactive", "content" to content(config(listOf(solid("satellite", "sphere")))),
            ))),
        ))
        assertEquals(SpatialShape.CONE, classic.interactiveByScene["surface"]?.spatialExperiment?.objects?.single()?.shape)
        assertEquals(SpatialShape.SPHERE, managed.interactiveByScene["planet"]?.spatialExperiment?.objects?.single()?.shape)
    }

    @Test
    fun geometryAndActionValidationKeepIncompatibleScenesInTheirWebRuntime() {
        fun read(widget: Map<String, Any?>) = ClassroomSpatialExperiment.fromWidgetConfig(widget)
        assertNull(read(config() - "nativeRenderer"))
        assertNull(read(config() + ("nativeRenderer" to "classroom-spatial/2")))
        assertNull(read(config(listOf(solid("asset", "custom")))))
        assertNull(read(config(listOf(solid("same", "sphere"), solid("same", "box")))))
        assertNull(read(config(List(17) { solid("obj_$it", "plane") })))
        assertNull(read(config() + ("interactions" to listOf(mapOf("type" to "slider", "target" to "camera")))))
        assertNull(read(config(listOf(solid("broken", "plane") + ("scale" to Double.NaN)))))
        val scene = requireNotNull(read(config()))
        assertTrue(scene.supportsActions(listOf(NativeAction("1", "widget_highlight", widgetTarget = "#cuboid"))))
        assertFalse(scene.supportsActions(listOf(NativeAction("1", "widget_highlight", widgetTarget = "#unknown"))))
        assertFalse(scene.supportsActions(listOf(NativeAction("2", "widget_setState", supported = false))))
    }

    @Test
    fun validLocalDataDoesNotRequireAnExternal3dCdn() {
        fun mode(kind: NativeRenderKind, reason: String? = null, ready: Boolean = true) = NativePlaybackPolicy.decide(
            renderKind = kind, sceneType = "interactive", hasDocument = true, hasRenderableContent = true,
            fallbackAvailable = true, renderReason = reason, hasNativeSpatialScene = ready,
        ).mode
        assertEquals(NativeSceneMode.NATIVE, mode(NativeRenderKind.SANDBOX_HTML))
        assertEquals(NativeSceneMode.NATIVE, mode(NativeRenderKind.UNSUPPORTED, "widget_requires_external_cdn"))
        assertEquals(NativeSceneMode.WEB_FALLBACK, mode(NativeRenderKind.UNSUPPORTED, "sandbox_policy_rejects_same_origin"))
        assertEquals(NativeSceneMode.SANDBOX_URL, mode(NativeRenderKind.SANDBOX_URL))
        assertEquals(NativeSceneMode.SANDBOX_HTML, mode(NativeRenderKind.SANDBOX_HTML, ready = false))
    }

    @Test
    fun eachSupportedSolidHasFacesAndDeclaredOrbitsMoveInDepth() {
        assertEquals(SpatialShape.entries.toSet(), ClassroomSpatialGeometry.meshes.keys)
        assertTrue(ClassroomSpatialGeometry.meshes.values.all { mesh ->
            mesh.faces.isNotEmpty() && mesh.faces.all { face -> face.all { it in mesh.vertices.indices } }
        })
        val body = solid("orb", "sphere") + mapOf(
            "position" to mapOf("x" to 2, "y" to 0, "z" to 0),
            "animation" to mapOf("type" to "orbit", "axis" to "y", "speed" to 1),
        )
        val experiment = requireNotNull(ClassroomSpatialExperiment.fromWidgetConfig(config(listOf(body))))
        val obj = experiment.objects.single()
        val before = ClassroomSpatialGeometry.worldTransform(obj, 0f)(SpatialVector.Zero)
        val after = ClassroomSpatialGeometry.worldTransform(obj, (Math.PI / 2).toFloat())(SpatialVector.Zero)
        assertEquals(2f, before.x, .01f)
        assertEquals(0f, after.x, .01f)
        assertEquals(-2f, after.z, .01f)
        assertTrue(ClassroomSpatialGeometry.bounds(experiment).second >= 2.5f)
    }
}
