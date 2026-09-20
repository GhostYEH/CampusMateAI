package com.example.campusai.data.remote.agent

import com.squareup.moshi.Json

/**
 * 学生世界模型的只读 DTO（与后端 /api/v1/learner-state 系列接口对齐）。
 *
 * 设计约束：
 * - 只解析页面真正要展示的字段。`value` / `state_comparison` 这类自由结构
 *   刻意不建模：Moshi 会忽略未知字段，避免为一个展示摘要引入多态适配器。
 * - 降级信息（`data_quality` / `warning_codes` / `limitations`）必须建模，
 *   否则页面只能显示"没有数据"，无法区分"真的没有"和"取不到"。
 */

/** 候选模型只读注解（与后端 `CandidateAnnotationOut` 对齐）。 */
data class CandidateAnnotationDto(
    val available: Boolean = false,
    @Json(name = "capability_name") val capabilityName: String = "",
    @Json(name = "capability_version") val capabilityVersion: String = "",
    val reason: String? = null,
    @Json(name = "inference_source") val inferenceSource: String = "DETERMINISTIC_FALLBACK",
    @Json(name = "model_key") val modelKey: String? = null,
    @Json(name = "model_version") val modelVersion: String? = null,
    @Json(name = "prompt_version") val promptVersion: String? = null,
    @Json(name = "input_digest") val inputDigest: String? = null,
    @Json(name = "shadow_run_id") val shadowRunId: String? = null,
    @Json(name = "used_fallback") val usedFallback: Boolean = false,
    @Json(name = "claim_codes") val claimCodes: List<String> = emptyList(),
    val summary: String? = null,
    @Json(name = "read_only") val readOnly: Boolean = true,
    @Json(name = "affects_production") val affectsProduction: Boolean = false,
)

/** 状态投影快照摘要（CORE / ACADEMIC / WORLD）。 */
data class LearnerStateSnapshotDto(
    @Json(name = "snapshot_id") val snapshotId: String = "",
    @Json(name = "state_type") val stateType: String = "",
    val confidence: Double = 0.0,
    @Json(name = "data_quality") val dataQuality: String = "unavailable",
    @Json(name = "projection_kind") val projectionKind: String = "CORE",
    @Json(name = "warning_codes") val warningCodes: List<String> = emptyList(),
    @Json(name = "evidence_count") val evidenceCount: Int = 0,
    @Json(name = "observed_through") val observedThrough: String? = null,
    @Json(name = "valid_until") val validUntil: String? = null,
)

data class LearnerStateSnapshotPageDto(
    val items: List<LearnerStateSnapshotDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @Json(name = "page_size") val pageSize: Int = 50,
    @Json(name = "has_more") val hasMore: Boolean = false,
)

/** 风险预测摘要。`value` 是多态结构，页面只需要概率/置信度/质量与限制说明。 */
data class ForecastDto(
    @Json(name = "forecast_id") val forecastId: String = "",
    @Json(name = "forecast_type") val forecastType: String = "",
    val probability: Double? = null,
    val confidence: Double = 0.0,
    @Json(name = "data_quality") val dataQuality: String = "unavailable",
    @Json(name = "horizon_end") val horizonEnd: String? = null,
    @Json(name = "explanation_codes") val explanationCodes: List<String> = emptyList(),
    val limitations: List<String> = emptyList(),
)

data class ForecastPageDto(
    val items: List<ForecastDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @Json(name = "page_size") val pageSize: Int = 20,
    @Json(name = "has_more") val hasMore: Boolean = false,
)

/** 数据源控制（只读消费；开关动作走既有 PUT 接口）。 */
data class DataSourceControlDto(
    @Json(name = "source_key") val sourceKey: String = "",
    val status: String = "ENABLED",
    @Json(name = "updated_at") val updatedAt: String? = null,
    @Json(name = "can_pause") val canPause: Boolean = true,
    @Json(name = "can_resume") val canResume: Boolean = true,
)

data class DataSourceControlListDto(
    val items: List<DataSourceControlDto> = emptyList(),
)

/** 模型透明度：能力状态 + "是否真的在影响生产"的诚实标记。 */
data class ModelCapabilityTransparencyDto(
    @Json(name = "capability_name") val capabilityName: String = "",
    @Json(name = "capability_version") val capabilityVersion: String = "",
    @Json(name = "production_method") val productionMethod: String = "",
    @Json(name = "campusmate_lm_status") val campusmateLmStatus: String = "SHADOW_ONLY",
    @Json(name = "quality_gate_passed") val qualityGatePassed: Boolean = false,
    @Json(name = "performance_gate_passed") val performanceGatePassed: Boolean = false,
    @Json(name = "performance_measured") val performanceMeasured: Boolean = false,
    @Json(name = "uses_real_model_inference") val usesRealModelInference: Boolean = false,
    @Json(name = "uses_fixed_prediction_file") val usesFixedPredictionFile: Boolean = true,
)

data class ModelTransparencyDto(
    val capabilities: List<ModelCapabilityTransparencyDto> = emptyList(),
    @Json(name = "campusmate_lm_enabled") val campusmateLmEnabled: Boolean = false,
    @Json(name = "campusmate_lm_affects_production") val campusmateLmAffectsProduction: Boolean = false,
    @Json(name = "shadow_results_modify_plans") val shadowResultsModifyPlans: Boolean = false,
    @Json(name = "read_only_canary_active") val readOnlyCanaryActive: Boolean = false,
    @Json(name = "uses_real_model_inference") val usesRealModelInference: Boolean = false,
    @Json(name = "uses_fixed_prediction_file") val usesFixedPredictionFile: Boolean = true,
    @Json(name = "real_inference_observed") val realInferenceObserved: Boolean = false,
    @Json(name = "fixture_only") val fixtureOnly: Boolean = false,
)

/** 干预记录（只读）。 */
data class AdaptiveInterventionDto(
    @Json(name = "intervention_id") val interventionId: String = "",
    @Json(name = "goal_id") val goalId: String = "",
    @Json(name = "plan_id") val planId: String? = null,
    /** `GOAL`：绑定真实学生目标；`PLAN`：普通计划未绑定目标，scope 是这份计划本身。 */
    @Json(name = "scope_type") val scopeType: String = "GOAL",
    val status: String = "",
    @Json(name = "strategy_code") val strategyCode: String = "",
    @Json(name = "strategy_version") val strategyVersion: String = "",
    @Json(name = "rationale_codes") val rationaleCodes: List<String> = emptyList(),
    @Json(name = "expected_outcomes") val expectedOutcomes: List<String> = emptyList(),
    val confidence: Double = 0.0,
    @Json(name = "problem_types") val problemTypes: List<String> = emptyList(),
    @Json(name = "data_quality") val dataQuality: String? = null,
    @Json(name = "warning_codes") val warningCodes: List<String> = emptyList(),
    @Json(name = "observation_due_at") val observationDueAt: String? = null,
    @Json(name = "outcome_verdict") val outcomeVerdict: String? = null,
    @Json(name = "superseded_by_intervention_id") val supersededByInterventionId: String? = null,
)

data class AdaptiveInterventionPageDto(
    val items: List<AdaptiveInterventionDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @Json(name = "page_size") val pageSize: Int = 20,
    @Json(name = "has_more") val hasMore: Boolean = false,
)

/**
 * 干预结果 + 系统决定（只读）。
 *
 * 页面只能展示后端**落库**的 `decision` / `decision_status`；
 * 只有 `decision_status == "APPLIED"` 才代表计划真的被替换。
 */
data class AdaptiveInterventionOutcomeDto(
    @Json(name = "intervention_id") val interventionId: String = "",
    @Json(name = "plan_id") val planId: String? = null,
    /** 见 [AdaptiveInterventionDto.scopeType]。两种范围都进入观测/评估/重规划闭环。 */
    @Json(name = "scope_type") val scopeType: String = "GOAL",
    @Json(name = "observation_status") val observationStatus: String = "NOT_STARTED",
    @Json(name = "execution_signal") val executionSignal: String = "NOT_STARTED",
    val adoption: String = "NOT_STARTED",
    val verdict: String = "NOT_OBSERVED",
    @Json(name = "observed_outcome") val observedOutcome: String = "INSUFFICIENT_EVIDENCE",
    @Json(name = "causal_claim") val causalClaim: String = "NOT_ESTIMATED",
    val decision: String? = null,
    @Json(name = "decision_reason_codes") val decisionReasonCodes: List<String> = emptyList(),
    @Json(name = "suggested_adjustments") val suggestedAdjustments: List<String> = emptyList(),
    @Json(name = "decision_status") val decisionStatus: String? = null,
    @Json(name = "observation_due_at") val observationDueAt: String? = null,
    @Json(name = "warning_codes") val warningCodes: List<String> = emptyList(),
)
