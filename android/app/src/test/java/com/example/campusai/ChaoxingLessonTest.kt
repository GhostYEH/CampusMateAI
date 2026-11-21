package com.example.campusai

import com.example.campusai.data.chaoxing.ChaoxingLesson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ChaoxingLessonTest {
    @Test fun parsesHomeworkReviewSlidesAndTransferQuestions() {
        val document: Map<String, Any?> = mapOf(
            "title" to "错题变式讲解",
            "scenes" to listOf<Any?>(
                mapOf(
                    "id" to "scene-slide",
                    "type" to "slide",
                    "title" to "先看方法",
                    "order" to 0,
                    "content" to mapOf(
                        "type" to "slide",
                        "slide" to mapOf(
                            "title" to "先看方法",
                            "sections" to listOf<Any?>(
                                mapOf(
                                    "heading" to "核心思路",
                                    "bullets" to listOf("先识别题型", "再列条件"),
                                ),
                            ),
                        ),
                    ),
                ),
                mapOf(
                    "id" to "scene-quiz",
                    "type" to "quiz",
                    "title" to "变式练习",
                    "order" to 1,
                    "content" to mapOf(
                        "type" to "quiz",
                        "questions" to listOf<Any?>(
                            mapOf(
                                "id" to "q1",
                                "type" to "single",
                                "question" to "下列哪一步先做？",
                                "options" to listOf<Any?>(
                                    mapOf("label" to "先整理条件", "value" to "A"),
                                    mapOf("label" to "直接背答案", "value" to "B"),
                                ),
                                "answer" to listOf("A"),
                                "analysis" to "先整理条件，再代入计算。",
                                "hints" to listOf("注意题目给了两个约束"),
                                "exerciseRole" to "transfer",
                                "sourceQuestionNumber" to 3,
                            ),
                        ),
                    ),
                ),
            ),
        )

        val lesson = ChaoxingLesson.fromDocument(document)
        requireNotNull(lesson)
        assertEquals("错题变式讲解", lesson.title)
        assertEquals(2, lesson.scenes.size)
        assertEquals(1, lesson.quizCount)
        assertEquals("核心思路", lesson.scenes[0].blocks.single().heading)
        assertEquals(listOf("先识别题型", "再列条件"), lesson.scenes[0].blocks.single().bullets)

        val question = lesson.scenes[1].questions.single()
        assertEquals("q1", question.id)
        assertEquals("下列哪一步先做？", question.prompt)
        assertEquals(2, question.options.size)
        assertEquals(listOf("A"), question.answer)
        assertEquals("先整理条件，再代入计算。", question.analysis)
        assertEquals(listOf("注意题目给了两个约束"), question.hints)
        assertEquals("transfer", question.exerciseRole)
        assertEquals(3, question.sourceNumber)
        assertTrue(question.isChoice)
        assertFalse(question.isMultiple)
        assertEquals("变式练习", question.roleLabel)
    }

    @Test fun parsesStringOptionsAndShortAnswerWithoutInventingAnAnswer() {
        val document: Map<String, Any?> = mapOf(
            "scenes" to listOf<Any?>(
                mapOf(
                    "id" to "quiz",
                    "type" to "quiz",
                    "content" to mapOf(
                        "questions" to listOf<Any?>(
                            mapOf(
                                "id" to "q1",
                                "type" to "single",
                                "question" to "选择",
                                "options" to listOf("A. 甲", "B. 乙"),
                                "answer" to "A",
                                "analysis" to "解析",
                            ),
                            mapOf(
                                "id" to "q2",
                                "type" to "short_answer",
                                "question" to "说明理由",
                                "answer" to emptyList<String>(),
                                "analysis" to "参考思路",
                            ),
                        ),
                    ),
                ),
            ),
        )

        val lesson = ChaoxingLesson.fromDocument(document)
        requireNotNull(lesson)
        val questions = lesson.scenes.single().questions
        assertEquals(listOf("A", "B"), questions[0].options.map { it.value })
        assertEquals(listOf("A"), questions[0].answer)
        assertEquals("参考思路", questions[1].analysis)
        assertTrue(questions[1].answer.isEmpty())
        assertFalse(questions[1].isChoice)
    }

    @Test fun rejectsDocumentsWithoutScenes() {
        assertNull(ChaoxingLesson.fromDocument(null))
        assertNull(ChaoxingLesson.fromDocument(mapOf<String, Any?>("scenes" to emptyList<Any?>())))
    }
}
