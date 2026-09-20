package com.example.campusai.ui.screens.agent

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 世界模型端侧消费的源码级契约测试。
 *
 * 为什么用源码断言而不是运行断言：本机没有 Android SDK platform-tools / adb / 模拟器，
 * 跑不了真机或模拟器验收。运行时行为无法验证时，至少要把**不可退让的安全边界**
 * 钉死在可离线执行的测试里：
 *
 * 1. 世界模型区块是**只读**的，唯一的写动作是数据源开关；
 * 2. 客户端不得创建或替换学习计划（计划变更只能由用户显式点击既有按钮触发，
 *    绝不能出现在世界模型区块里）；
 * 3. 反事实模拟在移动端是明确的只读降级说明，而不是一个点了没反应的按钮。
 */
class LearnerWorldModelSectionContractTest {

    private fun sourceFile(relative: String): File {
        // Gradle 单测的 workingDir 是模块目录（android/app），但为了稳妥，向上找一层。
        val candidates = listOf(File(relative), File("app/$relative"), File("../app/$relative"))
        return candidates.firstOrNull { it.exists() }
            ?: error("找不到源文件 $relative（cwd=${File(".").absolutePath}）")
    }

    private val section by lazy {
        sourceFile("src/main/java/com/example/campusai/ui/screens/agent/LearnerWorldModelSection.kt").readText()
    }
    private val apiService by lazy {
        sourceFile("src/main/java/com/example/campusai/data/remote/ApiService.kt").readText()
    }

    @Test
    fun `world model section never creates or replaces a learning plan`() {
        // 世界模型区块只能渲染只读数据 + 切换数据源；不得触碰任何计划写入能力。
        val forbidden = listOf(
            "createLearningGoalJob", "confirmPlan", "executePlan", "replan",
            "decideLearningPlan", "executeLearningPlan", "replanLearningPlan",
            "learning-plans", "adaptive-interventions",
        )
        for (token in forbidden) {
            assertFalse("世界模型区块不得出现计划写入能力：$token", section.contains(token))
        }
        // 它根本不应该拿到 repository（只通过回调暴露"数据源开关"这一件事）。
        assertFalse("世界模型区块不得持有 repository", section.contains("Repository"))
    }

    @Test
    fun `world model section exposes exactly one write action, the data source toggle`() {
        assertTrue(section.contains("onToggleSource"))
        // 只有 ENABLED / PAUSED 两种状态，不夹带删除或范围修改。
        assertTrue(section.contains("\"PAUSED\""))
        assertTrue(section.contains("\"ENABLED\""))
        // 注意不要用裸 "scope" 当禁用词：它会误伤合法的 `scopeType`（归因范围展示）。
        for (token in listOf(
            "requestDeletion", "delete-request", "deleteStatus",
            "MODEL_SHADOW_ONLY", "ALL_LEARNER_MODEL_DATA", "STATE_ONLY", "EVENTS_AND_STATE",
        )) {
            assertFalse("数据源控制不得夹带 $token", section.contains(token))
        }
    }

    @Test
    fun `counterfactual simulation stays an explicit read-only degradation`() {
        assertTrue(
            "必须给出明确的只读降级说明",
            section.contains("本端暂未提供反事实模拟入口；模拟是纯只读推演，不会执行干预。"),
        )
        assertFalse("未实现的模拟能力不得渲染可点击按钮", section.contains("运行模拟"))
        assertFalse("移动端不得持有模拟创建能力", section.contains("createSimulation"))
    }

    @Test
    fun `auto replan is only announced for the backend persisted APPLIED status`() {
        assertTrue(section.contains("decisionStatus"))
        assertTrue(section.contains("\"APPLIED\""))
        assertTrue(section.contains("已调整学习计划"))
        // 不得按 delta 或观测结论自行推断"已调整"。
        assertFalse("不得按 delta 猜测重规划结果", section.contains("delta >") || section.contains("delta <"))
    }

    @Test
    fun `intervention scope is stated for both GOAL and PLAN`() {
        assertTrue(section.contains("scopeType"))
        assertTrue(section.contains("\"PLAN\""))
        assertTrue(
            "无目标计划必须写明仍会安全替换计划",
            section.contains("有证据时同样会安全替换计划。"),
        )
    }

    @Test
    fun `learner state endpoints are read only except the data source switch`() {
        val lines = apiService.lines()
        lines.forEachIndexed { index, line ->
            if (line.contains("learner-state/") || line.contains("adaptive-interventions")) {
                val isWrite = Regex("""@(POST|PUT|PATCH|DELETE)""").containsMatchIn(line)
                val isDataSourceSwitch = line.contains("learner-state/data-controls")
                if (isWrite) {
                    assertTrue(
                        "第 ${index + 1} 行：learner-state 只允许 GET，唯一写操作是数据源开关：$line",
                        isDataSourceSwitch,
                    )
                }
            }
        }
    }
}
