package com.example.campusai.data.classroom.nativeplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomRewardsEngineTest {

    private val now = "2026-11-19T09:00:00Z"

    @Test
    fun `first visit awards once and duplicate visit is ignored`() {
        val first = ClassroomRewardsEngine.visit(
            rewards = ClassroomRewardsEngine.empty(),
            sceneId = "s1",
            totalScenes = 4,
            now = now,
        )
        assertEquals(ClassroomRewardsEngine.XP_PER_SCENE, first.awardedXp)
        assertTrue(first.unlocked.contains("first_scene"))

        val duplicate = ClassroomRewardsEngine.visit(
            rewards = first.state,
            sceneId = "s1",
            totalScenes = 4,
            now = now,
        )
        assertEquals(0, duplicate.awardedXp)
        assertEquals(first.state.xp, duplicate.state.xp)
        assertTrue(duplicate.unlocked.isEmpty())
    }

    @Test
    fun `half route unlocks at half coverage`() {
        var rewards = ClassroomRewardsEngine.empty()
        val visited = mutableListOf<String>()
        for (index in 0 until 3) {
            val result = ClassroomRewardsEngine.visit(rewards, "s$index", 5, now)
            visited += result.unlocked
            rewards = result.state
        }
        assertTrue(visited.contains("half_route"))
    }

    @Test
    fun `grade applies correct combo perfect bonus only once`() {
        val first = ClassroomRewardsEngine.grade(
            rewards = ClassroomRewardsEngine.empty(),
            sceneId = "quiz-1",
            correct = 3,
            total = 4,
            totalScenes = 4,
            now = now,
        )
        assertEquals(3 * ClassroomRewardsEngine.XP_PER_CORRECT, first.awardedXp)
        assertEquals(1, first.combo)
        assertFalse(first.state.quiz.getValue("quiz-1").perfect)

        val second = ClassroomRewardsEngine.grade(
            rewards = first.state,
            sceneId = "quiz-2",
            correct = 4,
            total = 4,
            totalScenes = 4,
            now = now,
        )
        assertEquals(
            4 * ClassroomRewardsEngine.XP_PER_CORRECT +
                ClassroomRewardsEngine.XP_PERFECT_BONUS +
                ClassroomRewardsEngine.XP_COMBO_BONUS,
            second.awardedXp,
        )
        assertEquals(2, second.combo)
        assertTrue(second.unlocked.contains("perfect_quiz"))

        val duplicate = ClassroomRewardsEngine.grade(
            rewards = second.state,
            sceneId = "quiz-1",
            correct = 0,
            total = 4,
            totalScenes = 4,
            now = now,
        )
        assertEquals(0, duplicate.awardedXp)
        assertEquals(second.state.xp, duplicate.state.xp)
        assertEquals(2, duplicate.state.combo)
    }

    @Test
    fun `wrong answer resets combo but keeps previous xp`() {
        val first = ClassroomRewardsEngine.grade(
            ClassroomRewardsEngine.empty(), "quiz-1", 4, 4, 4, now,
        )
        val wrong = ClassroomRewardsEngine.grade(first.state, "quiz-2", 0, 4, 4, now)
        assertEquals(0, wrong.state.combo)
        assertEquals(first.state.xp, wrong.state.xp)
    }

    @Test
    fun `level steps every 100 xp`() {
        val level = ClassroomRewardsEngine.levelOf(120)
        assertEquals(2, level.level)
        assertEquals(20, level.inLevel)
        assertEquals(80, level.toNext)
        assertEquals(0.2f, level.progress, 0.001f)
    }
}
