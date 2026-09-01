package com.example.campusai.data.focus.goal

import android.content.Context
import com.example.campusai.data.remote.TaskBreakdownResponseDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.util.UUID

data class FocusGoalStep(
    val number: Int,
    val title: String,
    val description: String,
    val estimatedMinutes: Int,
    val completionCriteria: String,
    val completed: Boolean = false,
)

data class FocusGoalPlan(
    val id: String = UUID.randomUUID().toString(),
    val goal: String,
    val analysis: String,
    val steps: List<FocusGoalStep>,
    val sourceMode: String = "rule_fallback",
    val warnings: List<String> = emptyList(),
    val sessionId: String? = null,
)

fun TaskBreakdownResponseDto.toFocusGoalPlan(): FocusGoalPlan {
    val normalizedSteps = steps.sortedBy { it.step_number }.map { step ->
        FocusGoalStep(step.step_number, step.title, step.description, step.estimated_minutes, step.completion_criteria)
    }
    val estimatedMinutes = normalizedSteps.sumOf { it.estimatedMinutes }
    val modeLabel = if (mode == "llm") "AI 已结合你的目标生成" else "已生成一份可执行的基础方案"
    val firstAction = normalizedSteps.firstOrNull()?.title ?: "从写下第一个动作开始"
    return FocusGoalPlan(
        goal = goal,
        analysis = "$modeLabel，共 ${normalizedSteps.size} 步，预计约 ${estimatedMinutes.coerceAtLeast(1)} 分钟。先从「$firstAction」开始，每完成一步再进入下一步。",
        steps = normalizedSteps,
        sourceMode = mode,
        warnings = warnings,
    )
}

class FocusGoalPlanStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences("focus_goal_plan", Context.MODE_PRIVATE)
    private val adapter = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build().adapter(FocusGoalPlan::class.java)

    fun load(): FocusGoalPlan? = preferences.getString(KEY_PLAN, null)?.let { encoded -> runCatching { adapter.fromJson(encoded) }.getOrNull() }
    fun save(plan: FocusGoalPlan) { preferences.edit().putString(KEY_PLAN, adapter.toJson(plan)).apply() }
    fun clear() { preferences.edit().remove(KEY_PLAN).apply() }

    private companion object { const val KEY_PLAN = "active_plan" }
}
