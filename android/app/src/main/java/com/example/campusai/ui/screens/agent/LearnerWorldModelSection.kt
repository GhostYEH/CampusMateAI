package com.example.campusai.ui.screens.agent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.campusai.data.remote.agent.CandidateAnnotationDto
import com.example.campusai.data.remote.agent.DataSourceControlDto
import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassCard as Card
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton

/**
 * 学生世界模型的移动端只读视图。
 *
 * 与 Web 对齐的展示契约：
 * - 状态摘要必须同时给出**数据质量与警告**，让"真的没有"和"取不到"能区分开；
 * - 候选模型（CampusMate-LM）结果必须标明来源，且不可用时只显示稳定降级原因；
 * - 自动重规划结果只展示后端**落库**的 `decision_status`，只有 `APPLIED`
 *   才显示"已调整学习计划"，不按差值自行推测；
 * - 反事实模拟本端未实现：给出明确的只读降级说明，而不是放一个空按钮。
 */
private val QUALITY_LABEL = mapOf(
    "verified" to "已验证",
    "partial" to "部分可信",
    "stale" to "已过期",
    "unavailable" to "不可用",
)

private val FORECAST_LABEL = mapOf(
    "DEADLINE_COMPLETION_RISK" to "截止风险",
    "UPCOMING_WORKLOAD" to "未来负载",
    "SCHEDULE_CONFLICT_RISK" to "日程冲突",
    "GOAL_PROGRESS_OUTLOOK" to "目标进展",
    "ROUTINE_CONTINUITY" to "作息连续性",
)

private val DECISION_LABEL = mapOf(
    "CONTINUE" to "继续当前计划",
    "WAIT_FOR_EVIDENCE" to "等待更多证据",
    "REPLAN" to "重新规划",
    "SUSPEND" to "暂停调整",
)

private val DECISION_STATUS_LABEL = mapOf(
    "APPLIED" to "已应用",
    "PENDING" to "待处理",
    "APPLYING" to "处理中",
    "FAILED" to "处理失败",
)

private val SOURCE_LABEL = mapOf(
    "CORE_STUDY" to "核心学习记录",
    "PERSONAL_TASK" to "个人待办",
    "CHAOXING" to "学习通",
    "EDU" to "教务系统",
    "MODEL_SHADOW" to "模型影子评测",
    "PROACTIVE_SUGGESTIONS" to "主动建议",
)

private val CANDIDATE_REASON_LABEL = mapOf(
    "canary_feature_flag_disabled" to "金丝雀展示未开启",
    "candidate_model_not_configured" to "候选模型未配置",
    "model_shadow_paused_for_user" to "你已暂停模型影子评测",
    "no_promotion_decision" to "候选模型尚未通过评测",
    "quality_gates_failed" to "候选模型未通过质量门控",
    "circuit_breaker_open" to "候选模型暂时熔断",
    "MODEL_RATE_LIMITED" to "本次未命中采样",
    "MODEL_TIMEOUT" to "候选模型响应超时",
    "MODEL_SCHEMA_INVALID" to "候选模型输出格式不合法",
    "MODEL_POLICY_VIOLATION" to "候选模型输出违反安全策略",
    "MODEL_DISABLED" to "候选模型未启用",
    "MODEL_UNAVAILABLE" to "候选模型不可用",
    "candidate_invocation_failed" to "候选模型调用失败",
    "no_eligible_feature_input" to "当前计划没有可用的结构化特征",
)

@Composable
fun CandidateAnnotationRow(annotation: CandidateAnnotationDto?) {
    if (annotation == null) return
    Column(Modifier.fillMaxWidth()) {
        Text(
            if (annotation.available) "候选模型建议（只读）" else "候选模型建议不可用",
            style = MaterialTheme.typography.labelLarge,
        )
        if (annotation.available) {
            annotation.summary?.let { Text(it) }
            if (annotation.claimCodes.isNotEmpty()) {
                Text("依据：${annotation.claimCodes.joinToString("、")}")
            }
            Text("来源：${annotation.modelKey ?: "未知"} · 提示版本 ${annotation.promptVersion ?: "未知"}")
        } else {
            Text("已回退到确定性结果：${CANDIDATE_REASON_LABEL[annotation.reason] ?: annotation.reason ?: "不可用"}")
        }
        Text(
            "这是候选模型的只读展示，不会修改你的状态、计划或待办。",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
fun WorldModelSection(
    state: WorldModelUiState,
    onToggleSource: (String, String) -> Unit,
    enabled: Boolean,
) {
    Card {
        Column(Modifier.padding(16.dp)) {
            Text("学生世界模型（只读）")
            Spacer(Modifier.height(4.dp))

            state.degradedReason?.let {
                Text("只读降级：$it", style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(6.dp))
            }

            if (state.loading) {
                Text("加载中…", style = MaterialTheme.typography.bodySmall)
                return@Column
            }

            // 1. 状态摘要 + 数据质量 / 警告
            Text("状态摘要", style = MaterialTheme.typography.labelLarge)
            if (state.snapshots.isEmpty()) {
                Text("暂无状态快照（可能是还没有可投影的学习记录）", style = MaterialTheme.typography.bodySmall)
            } else {
                state.snapshots.take(6).forEach { snapshot ->
                    val quality = QUALITY_LABEL[snapshot.dataQuality] ?: snapshot.dataQuality
                    Text("${snapshot.projectionKind} · ${snapshot.stateType} · 质量 $quality · 置信度 ${"%.2f".format(snapshot.confidence)}")
                    if (snapshot.warningCodes.isNotEmpty()) {
                        Text("警告：${snapshot.warningCodes.joinToString("、")}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Spacer(Modifier.height(8.dp))

            // 2. 预测摘要
            Text("风险预测", style = MaterialTheme.typography.labelLarge)
            if (state.forecasts.isEmpty()) {
                Text("暂无预测结果", style = MaterialTheme.typography.bodySmall)
            } else {
                state.forecasts.take(5).forEach { forecast ->
                    val probability = forecast.probability?.let { "${(it * 100).toInt()}%" } ?: "无概率"
                    val quality = QUALITY_LABEL[forecast.dataQuality] ?: forecast.dataQuality
                    Text("${FORECAST_LABEL[forecast.forecastType] ?: forecast.forecastType} · $probability · 质量 $quality")
                    if (forecast.limitations.isNotEmpty()) {
                        Text("限制：${forecast.limitations.joinToString("、")}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Spacer(Modifier.height(8.dp))

            // 3. 计划状态与自动重规划结果（只认后端落库的 decision_status）
            Text("计划与自动重规划", style = MaterialTheme.typography.labelLarge)
            val outcome = state.interventionOutcome
            if (outcome == null) {
                Text("确认计划后，系统会在观测窗结束后自动核对执行情况；只有证据支持时才会调整计划。", style = MaterialTheme.typography.bodySmall)
            } else {
                val status = outcome.decisionStatus
                Text(
                    if (status == "APPLIED") "系统决定：${DECISION_LABEL[outcome.decision] ?: outcome.decision ?: "未知"}（已调整学习计划）"
                    else "系统决定：${DECISION_LABEL[outcome.decision] ?: outcome.decision ?: "尚未产生"}（${DECISION_STATUS_LABEL[status] ?: status ?: "未处理"}）",
                )
                Text("观测：${outcome.observedOutcome} · 执行信号 ${outcome.executionSignal} · 归因 ${outcome.causalClaim}", style = MaterialTheme.typography.bodySmall)
                if (outcome.decisionReasonCodes.isNotEmpty()) {
                    Text("原因码：${outcome.decisionReasonCodes.joinToString("、")}", style = MaterialTheme.typography.bodySmall)
                }
            }
            Spacer(Modifier.height(8.dp))

            // 4. 反事实模拟：本端没有入口，给明确、安全的只读降级说明
            Text("反事实模拟", style = MaterialTheme.typography.labelLarge)
            Text("本端暂未提供反事实模拟入口；模拟是纯只读推演，不会执行干预。如需运行请在 Web 端「学习预测」页操作。", style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(8.dp))

            // 5. 数据源控制 + 模型透明度
            Text("数据源控制", style = MaterialTheme.typography.labelLarge)
            if (state.dataControls.isEmpty()) {
                Text("暂无可控制的数据源", style = MaterialTheme.typography.bodySmall)
            } else {
                state.dataControls.forEach { control: DataSourceControlDto ->
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text("${SOURCE_LABEL[control.sourceKey] ?: control.sourceKey} · ${if (control.status == "ENABLED") "已启用" else "已暂停"}")
                        if (control.status == "ENABLED" && control.canPause) {
                            OutlinedButton(onClick = { onToggleSource(control.sourceKey, "PAUSED") }, enabled = enabled) { Text("暂停") }
                        } else if (control.canResume) {
                            OutlinedButton(onClick = { onToggleSource(control.sourceKey, "ENABLED") }, enabled = enabled) { Text("恢复") }
                        }
                    }
                }
            }
            Spacer(Modifier.height(8.dp))

            Text("模型透明度", style = MaterialTheme.typography.labelLarge)
            val transparency = state.transparency
            if (transparency == null) {
                Text("暂无模型透明度数据", style = MaterialTheme.typography.bodySmall)
            } else {
                Text("CampusMate-LM 影响正式状态：${if (transparency.campusmateLmAffectsProduction) "是" else "否"}")
                Text("影子结果会修改计划：${if (transparency.shadowResultsModifyPlans) "是" else "否"}")
                Text("已观测到真实模型推理：${if (transparency.realInferenceObserved) "是" else "否（当前为固定预测文件）"}")
                transparency.capabilities.forEach { capability ->
                    Text(
                        "${capability.capabilityName} · ${capability.campusmateLmStatus} · 质量门控${if (capability.qualityGatePassed) "通过" else "未通过"}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}
