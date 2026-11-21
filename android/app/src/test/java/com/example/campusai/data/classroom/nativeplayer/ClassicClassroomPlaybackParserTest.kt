package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.ClassroomPlaybackSceneDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassicClassroomPlaybackParserTest {

    @Test
    fun `classic playback projects scenes into native document and plan`() {
        val slide = ClassroomPlaybackSceneDto(
            id = "slide-1",
            type = "slide",
            title = "第一页",
            order = 0,
            content = mapOf(
                "canvas" to mapOf(
                    "viewportSize" to 1000,
                    "elements" to listOf(
                        mapOf(
                            "id" to "text-1",
                            "type" to "text",
                            "left" to 40,
                            "top" to 50,
                            "width" to 400,
                            "height" to 80,
                            "content" to "课堂开始",
                        ),
                    ),
                ),
            ),
            render = mapOf("kind" to "native"),
        )
        val interactive = ClassroomPlaybackSceneDto(
            id = "interactive-1",
            type = "interactive",
            title = "互动",
            order = 1,
            content = mapOf("html" to "<p>拖动实验</p>"),
            render = mapOf("kind" to "sandbox-html", "sandbox" to "allow-scripts"),
            actions = listOf(
                mapOf(
                    "id" to "a1",
                    "type" to "widget_open",
                    "mode" to "sync",
                    "payload" to mapOf("element_id" to "widget-1"),
                ),
            ),
        )
        val dto = ClassroomPlaybackDto(
            courseId = "course-1",
            sessionId = "session-1",
            classroomId = "classroom-1",
            contentVersion = "v1",
            title = "经典课堂",
            startIndex = 1,
            scenes = listOf(slide, interactive),
        )

        val document = NativeClassroomParser.parsePlayback(dto)
        val plan = NativeClassroomParser.parsePlaybackPlan(dto)

        assertEquals("经典课堂", document.title)
        assertEquals(2, document.scenes.size)
        assertEquals(1, document.slideByScene["slide-1"]?.elements?.size)
        assertEquals("课堂开始", (document.slideByScene["slide-1"]?.elements?.first() as NativeCanvasElement.Text).plainText)
        assertEquals("widget-1", document.scenes[1].actions.first().elementId)
        assertEquals(NativeRenderKind.NATIVE, plan.scenes[0].renderKind)
        assertEquals(NativeRenderKind.SANDBOX_HTML, plan.scenes[1].renderKind)
        assertEquals("<p>拖动实验</p>", plan.scenes[1].sandboxPayload)
        assertEquals(1, plan.startIndex)
        assertTrue(plan.revision > 0)
    }

    @Test
    fun `classic playback rejects same-origin sandbox`() {
        val dto = ClassroomPlaybackDto(
            contentVersion = "v2",
            scenes = listOf(
                ClassroomPlaybackSceneDto(
                    id = "bad",
                    type = "interactive",
                    content = mapOf("html" to "<p>x</p>"),
                    render = mapOf("kind" to "sandbox-html", "sandbox" to "allow-scripts allow-same-origin"),
                ),
            ),
        )
        val plan = NativeClassroomParser.parsePlaybackPlan(dto)
        assertEquals(NativeRenderKind.UNSUPPORTED, plan.scenes.single().renderKind)
    }

    @Test
    fun `classic playback exposes speech audio and links steps to actions`() {
        val scene = ClassroomPlaybackSceneDto(
            id = "speech-scene",
            type = "slide",
            title = "讲解页",
            order = 0,
            content = mapOf("canvas" to mapOf("elements" to emptyList<Any>())),
            render = mapOf("kind" to "native"),
            actions = listOf(
                mapOf(
                    "id" to "a1",
                    "type" to "speech",
                    "payload" to mapOf(
                        "text" to "老师讲解",
                        "audioUrl" to "/api/v1/courses/course-1/interactive-classroom/session-1/media/audio/a.mp3",
                    ),
                ),
            ),
            steps = listOf(mapOf("action_id" to "a1", "type" to "speech", "mode" to "sync")),
        )
        val dto = ClassroomPlaybackDto(
            courseId = "course-1",
            sessionId = "session-1",
            contentVersion = "v3",
            scenes = listOf(scene),
        )

        val document = NativeClassroomParser.parsePlayback(dto)
        val plan = NativeClassroomParser.parsePlaybackPlan(dto)

        val action = document.scenes.single().actions.single()
        assertEquals("a1", action.id)
        assertEquals("老师讲解", action.speech)
        assertEquals(
            "/api/v1/courses/course-1/interactive-classroom/session-1/media/audio/a.mp3",
            action.audioUrl,
        )
        assertTrue(action.supported)
        assertEquals("a1", plan.scenes.single().steps.single().actionId)
    }

    @Test
    fun `unsupported action keeps backend reason`() {
        val scene = ClassroomPlaybackSceneDto(
            id = "unsupported-scene",
            type = "slide",
            content = mapOf("canvas" to mapOf("elements" to emptyList<Any>())),
            render = mapOf("kind" to "native"),
            actions = listOf(
                mapOf(
                    "id" to "a2",
                    "type" to "wb_draw_text",
                    "supported" to false,
                    "reason" to "whiteboard_runtime_missing",
                ),
            ),
        )
        val document = NativeClassroomParser.parsePlayback(
            ClassroomPlaybackDto(contentVersion = "v4", scenes = listOf(scene)),
        )

        val action = document.scenes.single().actions.single()
        assertFalse(action.supported)
        assertEquals("whiteboard_runtime_missing", action.reason)
    }
}
