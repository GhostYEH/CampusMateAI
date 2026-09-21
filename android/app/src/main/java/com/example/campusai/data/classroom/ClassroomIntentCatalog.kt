package com.example.campusai.data.classroom

import java.util.Locale

/**
 * 9 个学生生成意图（与后端 `MODE_INTENT_LABELS`、Web `INTERACTIVE_MODES` 一一对应）。
 *
 * 关键认知：magic class 的生成接口**只接受一个 requirement 字符串**，没有任何类型参数。
 * 所以这些 mode 只是"生成意图"，不承诺最终产出某种具体形式；真实组成必须回读
 * `GET /api/classroom?id=` 才知道（见 [ClassroomCompositionText]）。
 */
enum class ClassroomIntent(val wire: String, val label: String, val description: String) {
    ADAPTIVE("adaptive", "自动推荐", "按你的掌握情况与近期考试自动选择"),
    EXPLAIN("explain", "概念讲解", "把定义、直觉与推导一步步讲清楚"),
    QUIZ("quiz", "练习测验", "做题并即时看到解析，找到卡点"),
    SIMULATION("simulation", "实验模拟", "动手调参数、看结果变化"),
    VISUALIZATION("visualization", "3D/可视化", "把抽象结构看得见（需可访问外部 CDN）"),
    MINDMAP("mindmap", "思维导图", "梳理概念之间的关系与层级"),
    CODING("coding", "编程实验", "改代码、跑一跑，用代码验证结论"),
    PBL("pbl", "项目式学习", "用真实项目任务带动知识运用"),
    REVIEW("review", "考前复习", "优先补薄弱点与高频考点"),
}

object ClassroomIntentCatalog {

    /** 必须对学生明示：形态只是意图，不保证产出。 */
    const val INTENT_NOTE: String =
        "内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。"

    /** 旧值 → 新意图（后端同样会归一化；前端也要能独立处理）。 */
    private val LEGACY = mapOf(
        "explore" to ClassroomIntent.SIMULATION,
        "practice" to ClassroomIntent.QUIZ,
        "project" to ClassroomIntent.PBL,
    )

    val all: List<ClassroomIntent> = ClassroomIntent.entries.toList()

    /** 任意输入归一化到 9 个规范意图之一；无法识别时回落到 ADAPTIVE。 */
    fun normalize(mode: String?): ClassroomIntent {
        val text = mode?.trim()?.lowercase(Locale.ROOT).orEmpty()
        if (text.isEmpty()) return ClassroomIntent.ADAPTIVE
        ClassroomIntent.entries.firstOrNull { it.wire == text }?.let { return it }
        LEGACY[text]?.let { return it }
        return ClassroomIntent.ADAPTIVE
    }

    /** 是否是一个**被接受**的输入（含旧名）。用于校验而不是静默兜底。 */
    fun isAccepted(mode: String?): Boolean {
        val text = mode?.trim()?.lowercase(Locale.ROOT).orEmpty()
        if (text.isEmpty()) return true
        return ClassroomIntent.entries.any { it.wire == text } || LEGACY.containsKey(text)
    }

    fun labelOf(mode: String?): String = normalize(mode).label

    /**
     * 难度选项（与后端 `difficulty_level` 白名单一致）。
     * 未知值一律忽略，不把非法值回显到 UI。
     */
    val difficultyLevels: List<Pair<String, String>> = listOf(
        "beginner" to "入门",
        "standard" to "标准",
        "advanced" to "进阶",
    )

    fun difficultyLabel(value: String?): String? =
        difficultyLevels.firstOrNull { it.first == value?.trim()?.lowercase(Locale.ROOT) }?.second

    /** 时长白名单（后端限制 5..180）。 */
    val durationOptions: List<Int> = listOf(15, 30, 45, 60)

    fun normalizeDuration(minutes: Int?): Int? {
        val value = minutes ?: return null
        if (value < 5 || value > 180) return null
        return value
    }
}
