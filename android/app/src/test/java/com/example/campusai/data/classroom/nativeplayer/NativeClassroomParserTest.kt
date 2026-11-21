package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.MagicClassScenePlaybackDto
import com.example.campusai.data.remote.MagicClassStagePlaybackDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeClassroomParserTest {

    @Test
    fun `plan follows server order and clamps start index`() {
        val playback = MagicClassStagePlaybackDto(
            stageId = "stage",
            workspaceId = "workspace",
            title = "课堂",
            revision = 4,
            startIndex = 9,
            scenes = listOf(
                scene("b", 2, "sandbox-html", "sandbox=\"allow-scripts\" content"),
                scene("a", 1, "native", null),
                scene("c", 0, "sandbox-url", "https://classroom.example/embed"),
            ),
        )
        val plan = NativeClassroomParser.parsePlan(playback)
        assertEquals(listOf("c", "a", "b"), plan.scenes.map { it.id })
        assertEquals(2, plan.startIndex)
        assertEquals(NativeRenderKind.SANDBOX_URL, plan.scenes.first { it.id == "c" }.renderKind)
        assertEquals(NativeRenderKind.SANDBOX_HTML, plan.scenes.first { it.id == "b" }.renderKind)
        assertEquals(NativeRenderKind.NATIVE, plan.scenes.first { it.id == "a" }.renderKind)
    }

    @Test
    fun `sandbox with same origin is rejected`() {
        val playback = MagicClassStagePlaybackDto(
            stageId = "stage",
            workspaceId = "workspace",
            scenes = listOf(
                scene("a", 0, "sandbox-html", "sandbox=\"allow-scripts allow-same-origin\""),
            ),
        )
        val plan = NativeClassroomParser.parsePlan(playback)
        assertEquals(NativeRenderKind.UNSUPPORTED, plan.scenes.single().renderKind)
        assertEquals("sandbox_policy_rejects_same_origin", plan.scenes.single().renderReason)
        assertTrue(NativePlaybackPolicy.decide(
            renderKind = plan.scenes.single().renderKind,
            sceneType = "interactive",
            hasDocument = true,
            hasRenderableContent = true,
            fallbackAvailable = true,
        ).mode == NativeSceneMode.WEB_FALLBACK)
    }

    @Test
    fun `document projects slide quiz and pbl without losing source ids`() {
        val document = mapOf(
            "stage" to mapOf("title" to "第二章"),
            "scenes" to listOf(
                mapOf(
                    "id" to "slide-1",
                    "type" to "slide",
                    "title" to "开场",
                    "order" to 0,
                    "content" to mapOf(
                        "canvas" to mapOf(
                            "viewportSize" to 1000,
                            "viewportRatio" to 0.5625,
                            "elements" to listOf(
                                mapOf(
                                    "id" to "title",
                                    "type" to "text",
                                    "left" to 80,
                                    "top" to 40,
                                    "width" to 800,
                                    "height" to 80,
                                    "content" to "<p><b>真实课件</b></p>",
                                    "textType" to "title",
                                ),
                                mapOf(
                                    "id" to "line",
                                    "type" to "line",
                                    "left" to 80,
                                    "top" to 130,
                                    "width" to 800,
                                    "height" to 2,
                                    "start" to listOf(0, 0),
                                    "end" to listOf(800, 2),
                                    "color" to "#285B4B",
                                ),
                            ),
                        ),
                    ),
                ),
                mapOf(
                    "id" to "quiz-1",
                    "type" to "quiz",
                    "title" to "挑战",
                    "order" to 1,
                    "content" to mapOf(
                        "questions" to listOf(
                            mapOf(
                                "id" to "q1",
                                "type" to "single",
                                "question" to "1 + 1 = ?",
                                "options" to listOf(
                                    mapOf("value" to "2", "label" to "A"),
                                    mapOf("value" to "3", "label" to "B"),
                                ),
                                "answer" to listOf("2"),
                                "analysis" to "基础加法",
                                "hasAnswer" to true,
                                "points" to 2,
                            ),
                        ),
                    ),
                ),
                mapOf(
                    "id" to "pbl-1",
                    "type" to "pbl",
                    "title" to "项目",
                    "order" to 2,
                    "content" to mapOf(
                        "project" to mapOf(
                            "title" to "做一个实验",
                            "description" to "分组完成",
                            "milestones" to listOf(
                                mapOf(
                                    "title" to "准备",
                                    "status" to "completed",
                                    "tasks" to listOf(mapOf("title" to "列材料", "status" to "completed")),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
        val parsed = NativeClassroomParser.parseDocument(
            document = document,
            stageId = "stage",
            fallbackTitle = "fallback",
            revision = 4,
        )
        assertEquals("第二章", parsed.title)
        assertEquals(3, parsed.scenes.size)
        val slide = parsed.slideByScene.getValue("slide-1")
        assertEquals(2, slide.elements.size)
        assertTrue(slide.elements.first() is NativeCanvasElement.Text)
        assertEquals("真实课件", (slide.elements.first() as NativeCanvasElement.Text).plainText)
        assertTrue((slide.elements[1] as NativeCanvasElement.Line).strokeWidth >= 1.0)
        val quiz = parsed.quizByScene.getValue("quiz-1")
        assertEquals(1, quiz.questions.size)
        assertTrue(quiz.questions.single().autoGradable)
        assertEquals(listOf("2"), quiz.questions.single().answerKey)
        val pbl = parsed.pblByScene.getValue("pbl-1")
        assertEquals("做一个实验", pbl.title)
        assertEquals(1, pbl.milestones.size)
        assertFalse(pbl.milestones.single().tasks.isEmpty())
    }

    @Test
    fun `fixture quiz accepts prompt string options and numeric answer`() {
        val document = mapOf(
            "scenes" to listOf(
                mapOf(
                    "id" to "quiz",
                    "type" to "quiz",
                    "title" to "随堂测验",
                    "order" to 0,
                    "content" to mapOf(
                        "questions" to listOf(
                            mapOf(
                                "id" to "q1",
                                "type" to "single",
                                "prompt" to "函数在区间内单调递增的条件是？",
                                "options" to listOf("A", "B", "C", "D"),
                                "answer" to 0,
                                "analysis" to "看导数符号",
                            ),
                        ),
                    ),
                ),
            ),
        )
        val parsed = NativeClassroomParser.parseDocument(
            document = document,
            stageId = "stage",
            fallbackTitle = "fallback",
            revision = 0,
        )
        val question = parsed.quizByScene.getValue("quiz").questions.single()
        assertEquals("函数在区间内单调递增的条件是？", question.question)
        assertEquals(4, question.options.size)
        assertEquals("A", question.options.first().value)
        assertEquals(listOf("A"), question.answerKey)
        assertTrue(question.autoGradable)
        assertEquals("看导数符号", question.analysis)
    }

    private fun scene(id: String, order: Int, kind: String, sandbox: String?): MagicClassScenePlaybackDto =
        MagicClassScenePlaybackDto(
            id = id,
            type = if (kind == "native") "slide" else "interactive",
            title = id,
            order = order,
            render = buildMap {
                put("kind", kind)
                if (sandbox != null) put("sandbox", sandbox)
            },
        )
}
