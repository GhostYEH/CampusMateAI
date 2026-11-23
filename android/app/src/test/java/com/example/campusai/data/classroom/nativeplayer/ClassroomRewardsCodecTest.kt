package com.example.campusai.data.classroom.nativeplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class ClassroomRewardsCodecTest {

    @Test
    fun `intact ledger round trips every field`() {
        val rewards = ClassroomRewards(
            version = 3,
            xp = 128,
            visited = setOf("scene-a", "scene-b"),
            quiz = mapOf("quiz-a" to ClassroomQuizReward(correct = 3, total = 4, perfect = false)),
            combo = 2,
            bestCombo = 4,
            achievements = setOf("first_scene", "combo_3"),
            updatedAt = "2026-11-22T08:00:00Z",
        )

        val decoded = ClassroomRewardsCodec.decodeResult(ClassroomRewardsCodec.encode(rewards))

        assertTrue(decoded is ClassroomRewardsDecodeResult.Intact)
        assertEquals(rewards, decoded.rewards)
        assertTrue(decoded.allowsWrite)
    }

    @Test
    fun `missing ledger is distinct from an empty object`() {
        assertTrue(ClassroomRewardsCodec.decodeResult(null) is ClassroomRewardsDecodeResult.Missing)
        assertTrue(ClassroomRewardsCodec.decodeResult("") is ClassroomRewardsDecodeResult.Missing)

        val emptyObject = ClassroomRewardsCodec.decodeResult("{}")
        assertTrue(emptyObject is ClassroomRewardsDecodeResult.Partial)
        assertEquals(ClassroomRewardsEngine.empty(), emptyObject.rewards)
        assertTrue(emptyObject.allowsWrite)
    }

    @Test
    fun `mixed bad and good fields keep usable data but block overwrite`() {
        val raw = """
            {
              "version": 2,
              "xp": 120,
              "visited": {"scene-a": true, "scene-b": "yes"},
              "quiz": {"quiz-a": {"correct": 3, "total": 4, "perfect": false}, "quiz-b": "broken"},
              "combo": 2,
              "bestCombo": 3,
              "achievements": ["first_scene", 42],
              "updatedAt": "2026-11-22T08:00:00Z"
            }
        """.trimIndent()

        val decoded = ClassroomRewardsCodec.decodeResult(raw)

        assertTrue(decoded is ClassroomRewardsDecodeResult.Unreadable)
        val unreadable = decoded as ClassroomRewardsDecodeResult.Unreadable
        assertEquals(120, unreadable.rewards.xp)
        assertEquals(setOf("scene-a"), unreadable.rewards.visited)
        assertEquals(setOf("quiz-a"), unreadable.rewards.quiz.keys)
        assertEquals(setOf("first_scene"), unreadable.rewards.achievements)
        assertTrue(ClassroomRewardsIssue.VISITED_ENTRY_INVALID in unreadable.issues)
        assertTrue(ClassroomRewardsIssue.QUIZ_ENTRY_INVALID in unreadable.issues)
        assertTrue(ClassroomRewardsIssue.ACHIEVEMENTS_INVALID in unreadable.issues)
        assertFalse(decoded.allowsWrite)
    }

    @Test
    fun `damage in a non critical field still allows normalized writes`() {
        val raw = """
            {
              "version": 2,
              "xp": 120,
              "visited": {"scene-a": true},
              "quiz": {},
              "combo": 2,
              "bestCombo": 3,
              "achievements": [42],
              "updatedAt": "2026-11-22T08:00:00Z"
            }
        """.trimIndent()

        val decoded = ClassroomRewardsCodec.decodeResult(raw)

        assertTrue(decoded is ClassroomRewardsDecodeResult.Partial)
        val partial = decoded as ClassroomRewardsDecodeResult.Partial
        assertEquals(120, partial.rewards.xp)
        assertEquals(setOf("scene-a"), partial.rewards.visited)
        assertTrue(ClassroomRewardsIssue.ACHIEVEMENTS_INVALID in partial.issues)
        assertTrue(decoded.allowsWrite)
    }

    @Test
    fun `truncated json is unreadable and keeps no guessed rewards`() {
        val decoded = ClassroomRewardsCodec.decodeResult("""{"xp":120,"visited":{"scene-a":true""")

        assertTrue(decoded is ClassroomRewardsDecodeResult.Unreadable)
        val unreadable = decoded as ClassroomRewardsDecodeResult.Unreadable
        assertEquals(ClassroomRewardsEngine.empty(), unreadable.rewards)
        assertTrue(ClassroomRewardsIssue.ROOT_UNPARSEABLE in unreadable.issues)
        assertNotNull(unreadable.errorType)
        assertFalse(decoded.allowsWrite)
    }

    @Test
    fun `missing visited or xp in a populated ledger blocks overwrite`() {
        val raw = """{"quiz":{},"achievements":["first_scene"]}"""

        val decoded = ClassroomRewardsCodec.decodeResult(raw)

        assertTrue(decoded is ClassroomRewardsDecodeResult.Unreadable)
        val unreadable = decoded as ClassroomRewardsDecodeResult.Unreadable
        assertTrue(ClassroomRewardsIssue.VISITED_MISSING in unreadable.issues)
        assertTrue(ClassroomRewardsIssue.XP_MISSING in unreadable.issues)
        assertFalse(decoded.allowsWrite)
    }
}
