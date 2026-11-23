package com.example.campusai.data.classroom.nativeplayer

import org.json.JSONArray
import org.json.JSONObject

/**
 * 与 Web 课堂相同的奖励口径。规则是纯函数：首次访问某页 +12 XP；
 * 首次交卷按答对题数 ×6，满分 +20，连击从第二份起 +12；
 * 同一页重复访问/重复交卷不再结算。这样原生与兼容播放切换时不会重复加分。
 */
data class ClassroomQuizReward(
    val correct: Int,
    val total: Int,
    val perfect: Boolean,
)

data class ClassroomRewards(
    val version: Int = ClassroomRewardsEngine.REWARD_VERSION,
    val xp: Int = 0,
    val visited: Set<String> = emptySet(),
    val quiz: Map<String, ClassroomQuizReward> = emptyMap(),
    val combo: Int = 0,
    val bestCombo: Int = 0,
    val achievements: Set<String> = emptySet(),
    val updatedAt: String = "",
)

data class ClassroomRewardResult(
    val state: ClassroomRewards,
    val awardedXp: Int,
    val unlocked: List<String>,
    val combo: Int = 0,
)

data class ClassroomLevel(
    val level: Int,
    val xp: Int,
    val inLevel: Int,
    val toNext: Int,
    val progress: Float,
)

object ClassroomRewardsEngine {
    const val REWARD_VERSION = 1
    const val XP_PER_SCENE = 12
    const val XP_PER_CORRECT = 6
    const val XP_PERFECT_BONUS = 20
    const val XP_COMBO_BONUS = 12
    const val LEVEL_STEP = 100

    private val achievementIds = setOf(
        "first_scene",
        "half_route",
        "finish_route",
        "combo_3",
        "combo_5",
        "perfect_quiz",
    )

    fun empty(): ClassroomRewards = ClassroomRewards()

    fun normalize(raw: ClassroomRewards): ClassroomRewards {
        val visited = raw.visited.filter { it.isNotBlank() }.toSet()
        val quiz = raw.quiz.filterKeys { it.isNotBlank() }
        return ClassroomRewards(
            version = REWARD_VERSION,
            xp = raw.xp.coerceAtLeast(0),
            visited = visited,
            quiz = quiz,
            combo = raw.combo.coerceAtLeast(0),
            bestCombo = raw.bestCombo.coerceAtLeast(0),
            achievements = raw.achievements.filter { it in achievementIds }.toSet(),
            updatedAt = raw.updatedAt,
        )
    }

    fun levelOf(xp: Int): ClassroomLevel {
        val total = xp.coerceAtLeast(0)
        val level = total / LEVEL_STEP + 1
        val inLevel = total % LEVEL_STEP
        return ClassroomLevel(
            level = level,
            xp = total,
            inLevel = inLevel,
            toNext = LEVEL_STEP - inLevel,
            progress = inLevel / LEVEL_STEP.toFloat(),
        )
    }

    fun visit(
        rewards: ClassroomRewards,
        sceneId: String,
        totalScenes: Int,
        now: String,
    ): ClassroomRewardResult {
        val current = normalize(rewards)
        if (sceneId.isBlank() || sceneId in current.visited) {
            return ClassroomRewardResult(current, 0, emptyList(), current.combo)
        }
        val next = current.copy(
            xp = current.xp + XP_PER_SCENE,
            visited = current.visited + sceneId,
        )
        return withUnlocks(next, totalScenes, XP_PER_SCENE, now)
    }

    fun grade(
        rewards: ClassroomRewards,
        sceneId: String,
        correct: Int,
        total: Int,
        totalScenes: Int,
        now: String,
    ): ClassroomRewardResult {
        val current = normalize(rewards)
        val safeCorrect = correct.coerceAtLeast(0)
        val safeTotal = if (total > 0) total else safeCorrect
        val right = if (safeTotal > 0) safeCorrect.coerceAtMost(safeTotal) else 0
        if (sceneId.isBlank() || sceneId in current.quiz || safeTotal == 0) {
            return ClassroomRewardResult(current, 0, emptyList(), current.combo)
        }
        val perfect = right == safeTotal && safeTotal > 0
        val combo = if (right > 0) current.combo + 1 else 0
        val xp = right * XP_PER_CORRECT +
            (if (perfect) XP_PERFECT_BONUS else 0) +
            (if (right > 0 && combo > 1) XP_COMBO_BONUS else 0)
        val next = current.copy(
            xp = current.xp + xp,
            combo = combo,
            bestCombo = current.bestCombo.coerceAtLeast(combo),
            quiz = current.quiz + (sceneId to ClassroomQuizReward(right, safeTotal, perfect)),
        )
        return withUnlocks(next, totalScenes, xp, now).copy(combo = combo)
    }

    fun achievementLabel(id: String): String = when (id) {
        "first_scene" -> "开课了"
        "half_route" -> "过半"
        "finish_route" -> "走完这一章"
        "combo_3" -> "三连对"
        "combo_5" -> "五连对"
        "perfect_quiz" -> "满分答卷"
        else -> id
    }

    fun achievementDetail(id: String): String = when (id) {
        "first_scene" -> "完成第一页课堂内容"
        "half_route" -> "完成一半以上的页面"
        "finish_route" -> "完成本章全部页面"
        "combo_3" -> "连续答对三份测验"
        "combo_5" -> "连续答对五份测验"
        "perfect_quiz" -> "一份测验全部答对"
        else -> ""
    }

    private fun withUnlocks(
        state: ClassroomRewards,
        totalScenes: Int,
        awarded: Int,
        now: String,
    ): ClassroomRewardResult {
        val unlocked = unlockedAchievements(state, totalScenes)
        if (unlocked.isEmpty()) {
            return ClassroomRewardResult(state, awarded, emptyList(), state.combo)
        }
        return ClassroomRewardResult(
            state = state.copy(
                achievements = state.achievements + unlocked,
                updatedAt = now,
            ),
            awardedXp = awarded,
            unlocked = unlocked,
            combo = state.combo,
        )
    }

    private fun unlockedAchievements(state: ClassroomRewards, totalScenes: Int): List<String> {
        val next = mutableListOf<String>()
        val earned = state.achievements
        fun add(id: String, condition: Boolean) {
            if (condition && id !in earned) next += id
        }
        add("first_scene", state.visited.size >= 1)
        add("half_route", totalScenes >= 2 && state.visited.size >= (totalScenes + 1) / 2)
        add("finish_route", totalScenes > 0 && state.visited.size >= totalScenes)
        add("combo_3", state.bestCombo >= 3)
        add("combo_5", state.bestCombo >= 5)
        add("perfect_quiz", state.quiz.values.any { it.perfect })
        return next
    }
}

/** 奖励账本的字段级问题；用于区分可归一化的坏字段与不能安全覆盖的损坏。 */
enum class ClassroomRewardsIssue {
    ROOT_UNPARSEABLE,
    XP_MISSING,
    XP_INVALID,
    VISITED_MISSING,
    VISITED_INVALID,
    VISITED_ENTRY_INVALID,
    QUIZ_MISSING,
    QUIZ_INVALID,
    QUIZ_ENTRY_INVALID,
    NUMBER_INVALID,
    ACHIEVEMENTS_INVALID,
}

/**
 * 账本解码结果。
 *
 * - [Missing]：确实没有账本，可按首次到访处理；
 * - [Intact]：整份可用；
 * - [Partial]：个别非关键字段被丢弃，去重依据（visited/quiz）仍可靠，可以继续写入归一化后的账本；
 * - [Unreadable]：整份无法解析，或 visited/quiz/xp 等去重依据无法可靠恢复。调用方必须保留原文，
 *   暂停受影响的自动结算和覆盖写入。
 */
sealed interface ClassroomRewardsDecodeResult {
    data object Missing : ClassroomRewardsDecodeResult

    data class Intact(val rewards: ClassroomRewards) : ClassroomRewardsDecodeResult

    data class Partial(
        val rewards: ClassroomRewards,
        val issues: List<ClassroomRewardsIssue>,
    ) : ClassroomRewardsDecodeResult

    data class Unreadable(
        val rewards: ClassroomRewards,
        val issues: List<ClassroomRewardsIssue>,
        val errorType: String? = null,
    ) : ClassroomRewardsDecodeResult
}

val ClassroomRewardsDecodeResult.rewards: ClassroomRewards?
    get() = when (this) {
        ClassroomRewardsDecodeResult.Missing -> null
        is ClassroomRewardsDecodeResult.Intact -> rewards
        is ClassroomRewardsDecodeResult.Partial -> rewards
        is ClassroomRewardsDecodeResult.Unreadable -> rewards
    }

/** 只有去重依据可靠时才允许自动结算与覆盖写入。 */
val ClassroomRewardsDecodeResult.allowsWrite: Boolean
    get() = this !is ClassroomRewardsDecodeResult.Unreadable

/** 只在本地持久层使用的 JSON 编解码；坏字段逐项丢弃，不整份重置。 */
object ClassroomRewardsCodec {

    fun decodeResult(raw: String?): ClassroomRewardsDecodeResult {
        if (raw.isNullOrBlank()) return ClassroomRewardsDecodeResult.Missing
        val root = try {
            JSONObject(raw)
        } catch (error: Exception) {
            return ClassroomRewardsDecodeResult.Unreadable(
                rewards = ClassroomRewardsEngine.empty(),
                issues = listOf(ClassroomRewardsIssue.ROOT_UNPARSEABLE),
                errorType = error.javaClass.simpleName,
            )
        }

        val critical = mutableListOf<ClassroomRewardsIssue>()
        val partial = mutableListOf<ClassroomRewardsIssue>()

        fun hasContent(): Boolean {
            if (root.numberOrNull("xp")?.let { it != 0 } == true) return true
            if (root.optJSONObject("visited")?.length()?.let { it > 0 } == true) return true
            if (root.optJSONObject("quiz")?.length()?.let { it > 0 } == true) return true
            if (root.optJSONArray("achievements")?.length()?.let { it > 0 } == true) return true
            return false
        }

        val visited = mutableSetOf<String>()
        when (val visitedValue = root.opt("visited")) {
            is JSONObject -> visitedValue.keys().forEach { key ->
                when (visitedValue.opt(key)) {
                    true -> visited += key
                    false -> Unit
                    else -> critical += ClassroomRewardsIssue.VISITED_ENTRY_INVALID
                }
            }
            null -> when {
                root.has("visited") -> critical += ClassroomRewardsIssue.VISITED_INVALID
                hasContent() -> critical += ClassroomRewardsIssue.VISITED_MISSING
                else -> partial += ClassroomRewardsIssue.VISITED_MISSING
            }
            else -> critical += ClassroomRewardsIssue.VISITED_INVALID
        }

        val quiz = mutableMapOf<String, ClassroomQuizReward>()
        when (val quizValue = root.opt("quiz")) {
            is JSONObject -> quizValue.keys().forEach { key ->
                val item = quizValue.opt(key)
                if (item !is JSONObject) {
                    critical += ClassroomRewardsIssue.QUIZ_ENTRY_INVALID
                    return@forEach
                }
                val correct = item.numberOrNull("correct")
                val total = item.numberOrNull("total")
                if (correct == null || total == null) {
                    critical += ClassroomRewardsIssue.QUIZ_ENTRY_INVALID
                    return@forEach
                }
                quiz[key] = ClassroomQuizReward(
                    correct = correct.coerceAtLeast(0),
                    total = total.coerceAtLeast(0),
                    perfect = item.opt("perfect") == true,
                )
            }
            null -> when {
                root.has("quiz") -> critical += ClassroomRewardsIssue.QUIZ_INVALID
                hasContent() -> critical += ClassroomRewardsIssue.QUIZ_MISSING
                else -> partial += ClassroomRewardsIssue.QUIZ_MISSING
            }
            else -> critical += ClassroomRewardsIssue.QUIZ_INVALID
        }

        val achievements = mutableSetOf<String>()
        when (val achievementsValue = root.opt("achievements")) {
            is JSONArray -> (0 until achievementsValue.length()).forEach { index ->
                val value = achievementsValue.opt(index)
                if (value is String && value.isNotBlank()) {
                    achievements += value
                } else {
                    partial += ClassroomRewardsIssue.ACHIEVEMENTS_INVALID
                }
            }
            null -> if (root.has("achievements")) partial += ClassroomRewardsIssue.ACHIEVEMENTS_INVALID
            else -> partial += ClassroomRewardsIssue.ACHIEVEMENTS_INVALID
        }

        val xp = when {
            !root.has("xp") -> {
                if (hasContent()) {
                    critical += ClassroomRewardsIssue.XP_MISSING
                }
                0
            }
            root.numberOrNull("xp") != null -> root.numberOrNull("xp")!!.coerceAtLeast(0)
            else -> {
                critical += ClassroomRewardsIssue.XP_INVALID
                0
            }
        }

        fun optionalNumber(key: String, default: Int): Int {
            if (!root.has(key)) return default
            val value = root.numberOrNull(key)
            if (value == null) {
                partial += ClassroomRewardsIssue.NUMBER_INVALID
                return default
            }
            return value
        }

        val rewards = ClassroomRewards(
            version = optionalNumber("version", ClassroomRewardsEngine.REWARD_VERSION),
            xp = xp,
            visited = visited,
            quiz = quiz,
            combo = optionalNumber("combo", 0).coerceAtLeast(0),
            bestCombo = optionalNumber("bestCombo", 0).coerceAtLeast(0),
            achievements = achievements,
            updatedAt = (root.opt("updatedAt") as? String).orEmpty(),
        )
        val issues = (critical + partial).distinct()
        return when {
            critical.isNotEmpty() -> ClassroomRewardsDecodeResult.Unreadable(rewards, issues)
            partial.isNotEmpty() -> ClassroomRewardsDecodeResult.Partial(rewards, issues)
            else -> ClassroomRewardsDecodeResult.Intact(rewards)
        }
    }

    /** 兼容旧调用：解码失败时仍返回可用于展示的空账本，写入前必须判断 [allowsWrite]。 */
    fun decode(raw: String?): ClassroomRewards =
        decodeResult(raw).rewards ?: ClassroomRewardsEngine.empty()

    fun encode(rewards: ClassroomRewards): String {
        val visited = JSONObject()
        rewards.visited.forEach { visited.put(it, true) }
        val quiz = JSONObject()
        rewards.quiz.forEach { (sceneId, reward) ->
            quiz.put(sceneId, JSONObject().apply {
                put("correct", reward.correct)
                put("total", reward.total)
                put("perfect", reward.perfect)
            })
        }
        val achievements = JSONArray()
        rewards.achievements.forEach { achievements.put(it) }
        return JSONObject().apply {
            put("version", rewards.version)
            put("xp", rewards.xp)
            put("visited", visited)
            put("quiz", quiz)
            put("combo", rewards.combo)
            put("bestCombo", rewards.bestCombo)
            put("achievements", achievements)
            put("updatedAt", rewards.updatedAt)
        }.toString()
    }
}

private fun JSONObject.numberOrNull(key: String): Int? {
    if (!has(key)) return null
    return when (val value = opt(key)) {
        is Number -> value.toInt()
        is String -> value.toIntOrNull()
        else -> null
    }
}
