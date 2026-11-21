package com.example.campusai.data.classroom.nativeplayer

import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * 跨端奖励契约：同一份事件样例同时驱动 Kotlin 原生引擎与网页脚本。
 * 任一端的 XP、连击、成就口径漂移都会在这里失败。
 */
class ClassroomRewardsContractTest {
    private val adapter = Moshi.Builder().build().adapter<Map<String, Any?>>(
        Types.newParameterizedType(Map::class.java, String::class.java, Any::class.java),
    )

    private fun find(vararg paths: String): File =
        paths.map(::File).firstOrNull { it.exists() }
            ?: error("找不到奖励契约文件：${paths.joinToString()}")

    private fun Map<String, Any?>.int(key: String): Int = (this[key] as? Number)?.toInt() ?: 0

    private fun Map<String, Any?>.strings(key: String): List<String> =
        (this[key] as? List<*>)?.map { it.toString() }.orEmpty()

    @Test
    fun `shared fixture drives the native engine`() {
        val fixtureFile = find(
            "src/test/resources/classroom-rewards-events.json",
            "app/src/test/resources/classroom-rewards-events.json",
        )
        val fixture = adapter.fromJson(fixtureFile.readText(Charsets.UTF_8))!!
        val scenes = fixture.int("scenes")
        val events = fixture["events"] as List<Map<String, Any?>>
        var state = ClassroomRewardsEngine.empty()

        events.forEachIndexed { index, event ->
            val expect = event["expect"] as Map<String, Any?>
            val scene = event["scene"].toString()
            val result = if (event["type"] == "visit") {
                ClassroomRewardsEngine.visit(state, scene, scenes, "2026-11-21T00:00:00Z")
            } else {
                ClassroomRewardsEngine.grade(
                    state, scene, event.int("correct"), event.int("total"), scenes,
                    "2026-11-21T00:00:00Z",
                )
            }
            assertEquals("event $index awardedXp", expect.int("awardedXp"), result.awardedXp)
            assertEquals("event $index xp", expect.int("xp"), result.state.xp)
            assertEquals("event $index combo", expect.int("combo"), result.combo)
            assertEquals("event $index unlocked", expect.strings("unlocked").toSet(), result.unlocked.toSet())
            state = result.state
        }

        val final = fixture["final"] as Map<String, Any?>
        assertEquals(final.int("xp"), state.xp)
        assertEquals(final.int("visited"), state.visited.size)
        assertEquals(final.int("quizCount"), state.quiz.size)
        assertEquals(final.int("combo"), state.combo)
        assertEquals(final.int("bestCombo"), state.bestCombo)
        assertEquals(final.strings("achievements").toSet(), state.achievements)
        val level = ClassroomRewardsEngine.levelOf(state.xp)
        assertEquals(final.int("level"), level.level)
        assertEquals(final.int("inLevel"), level.inLevel)
    }

    @Test
    fun `web script carries the same rule constants and achievement ids`() {
        val script = find(
            "src/main/assets/classroom-rewards.js",
            "app/src/main/assets/classroom-rewards.js",
        ).readText(Charsets.UTF_8)

        fun assertConstant(name: String, value: Int) {
            assertTrue(
                "$name 应与原生常量 $value 一致",
                Regex("var\\s+$name\\s*=\\s*$value\\b").containsMatchIn(script),
            )
        }
        assertConstant("VISIT_XP", ClassroomRewardsEngine.XP_PER_SCENE)
        assertConstant("CORRECT_XP", ClassroomRewardsEngine.XP_PER_CORRECT)
        assertConstant("PERFECT_BONUS", ClassroomRewardsEngine.XP_PERFECT_BONUS)
        assertConstant("COMBO_BONUS", ClassroomRewardsEngine.XP_COMBO_BONUS)
        assertConstant("LEVEL_STEP", ClassroomRewardsEngine.LEVEL_STEP)

        listOf("first_scene", "half_route", "finish_route", "combo_3", "combo_5", "perfect_quiz")
            .forEach { id ->
                assertTrue("脚本缺少成就 $id", script.contains("$id:"))
            }
        assertTrue("脚本必须按稳定场景身份记账", script.contains("data-scene-id"))
        assertTrue("脚本必须读取按服务/账号/课堂隔离的 key", script.contains("__campusRewardsConfig"))
        assertTrue("旧版 v1 账本不能被删除", script.contains("campusmate:classroom-rewards:v1"))
    }

    @Test
    fun `iOS script copy matches the canonical asset`() {
        val canonical = find(
            "src/main/assets/classroom-rewards.js",
            "app/src/main/assets/classroom-rewards.js",
        ).readText(Charsets.UTF_8)
        val ios = find(
            "../../ios/CampusMate/Resources/classroom-rewards.js",
            "ios/CampusMate/Resources/classroom-rewards.js",
        ).readText(Charsets.UTF_8)
        assertEquals("iOS 与 Android 的奖励脚本必须逐字一致", canonical, ios)
    }
}
