package com.example.campusai.data.remote.agent

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 世界模型 DTO 契约测试。
 *
 * 用**后端真实返回形状**（含自由结构的 `value` 字段）验证：
 * 1. 页面需要的字段都能解析出来；
 * 2. 未知/未建模字段（如 `value`）不会导致解析失败；
 * 3. 降级标记（`data_quality` / `warning_codes` / `limitations`）不会丢；
 * 4. 候选注解在不可用时只带稳定 reason，不带任何候选文本。
 */
class LearnerWorldModelDtoTest {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()

    @Test
    fun `plan summary parses candidate annotation and keeps read only flags`() {
        val json = """
        {"plan_id":"plan_1","goal_id":null,"status":"PROPOSED","stage":"AWAITING_CONFIRMATION",
         "headline":"计划草案已生成，等待学生确认","completion_percent":0,
         "planned_item_count":2,"executed_item_count":0,"planned_minutes":60,
         "next_action":"确认计划后创建个人待办","recommendations":[],
         "warning_codes":["data_quality_partial"],"generated_at":"2026-09-20T10:00:00+00:00",
         "candidate_annotation":{"available":true,"capability_name":"learning_summary_v1",
          "capability_version":"v1","reason":null,"inference_source":"REAL_MODEL",
          "model_key":"campusmate-lm","model_version":"candidate-v1",
          "prompt_version":"learning_summary_v1-prompt-v1","input_digest":"abc",
          "shadow_run_id":"shadow_1","used_fallback":false,
          "claim_codes":["PRIORITIZE_NEAR_DEADLINE"],"summary":"建议按已提供的优先级安排短时学习。",
          "read_only":true,"affects_production":false}}
        """.trimIndent()
        val summary = moshi.adapter(LearningPlanSummaryDto::class.java).fromJson(json)!!
        assertEquals("plan_1", summary.planId)
        assertEquals(listOf("data_quality_partial"), summary.warningCodes)
        val annotation = summary.candidateAnnotation
        assertNotNull(annotation)
        assertTrue(annotation!!.available)
        assertEquals("REAL_MODEL", annotation.inferenceSource)
        assertEquals("shadow_1", annotation.shadowRunId)
        assertTrue(annotation.readOnly)
        assertFalse(annotation.affectsProduction)
    }

    @Test
    fun `degraded candidate annotation carries a stable reason and no candidate text`() {
        val json = """
        {"plan_id":"plan_2","status":"PROPOSED","stage":"AWAITING_CONFIRMATION","headline":"h",
         "completion_percent":0,"planned_item_count":0,"executed_item_count":0,"planned_minutes":0,
         "next_action":"n","recommendations":[],"warning_codes":[],"generated_at":"2026-09-20T10:00:00+00:00",
         "candidate_annotation":{"available":false,"capability_name":"learning_summary_v1",
          "capability_version":"v1","reason":"MODEL_TIMEOUT","inference_source":"DETERMINISTIC_FALLBACK",
          "model_key":null,"model_version":null,"prompt_version":null,"input_digest":null,
          "shadow_run_id":null,"used_fallback":true,"claim_codes":[],"summary":null,
          "read_only":true,"affects_production":false}}
        """.trimIndent()
        val annotation = moshi.adapter(LearningPlanSummaryDto::class.java).fromJson(json)!!.candidateAnnotation!!
        assertFalse(annotation.available)
        assertEquals("MODEL_TIMEOUT", annotation.reason)
        assertTrue(annotation.usedFallback)
        assertNull(annotation.summary)
        assertTrue(annotation.claimCodes.isEmpty())
    }

    @Test
    fun `summary without candidate annotation stays null instead of failing`() {
        val json = """
        {"plan_id":"plan_3","status":"PROPOSED","stage":"AWAITING_CONFIRMATION","headline":"h",
         "completion_percent":0,"planned_item_count":0,"executed_item_count":0,"planned_minutes":0,
         "next_action":"n","recommendations":[],"warning_codes":[],"generated_at":"2026-09-20T10:00:00+00:00"}
        """.trimIndent()
        assertNull(moshi.adapter(LearningPlanSummaryDto::class.java).fromJson(json)!!.candidateAnnotation)
    }

    @Test
    fun `snapshot page parses quality warnings and ignores free form value`() {
        val json = """
        {"items":[{"snapshot_id":"lsnap_1","run_id":"lrun_1","scope_type":"USER","scope_id":"u1",
          "state_type":"task_workload","value":{"pending_task_count":3},"confidence":0.6,
          "data_quality":"partial","observed_from":"2026-09-01T00:00:00+00:00",
          "observed_through":"2026-09-20T00:00:00+00:00","valid_until":"2026-09-21T00:00:00+00:00",
          "computed_at":"2026-09-20T00:00:00+00:00","estimator_version":"deterministic-observed-v1",
          "projection_kind":"CORE","projection_scope":"__user__","input_digest":"d",
          "as_of":"2026-09-20T00:00:00+00:00","warning_codes":["learner_data_source_paused"],
          "evidence_count":2}],"total":1,"page":1,"page_size":50,"has_more":false}
        """.trimIndent()
        val page = moshi.adapter(LearnerStateSnapshotPageDto::class.java).fromJson(json)!!
        val snapshot = page.items.single()
        assertEquals("task_workload", snapshot.stateType)
        assertEquals("partial", snapshot.dataQuality)
        assertEquals(listOf("learner_data_source_paused"), snapshot.warningCodes)
        assertEquals(2, snapshot.evidenceCount)
    }

    @Test
    fun `forecast page parses limitations and tolerates the polymorphic value`() {
        val json = """
        {"items":[{"forecast_id":"fc_1","forecast_type":"UPCOMING_WORKLOAD","scope_type":"USER",
          "scope_id":"u1","horizon_start":"2026-09-20T00:00:00+00:00","horizon_end":"2026-09-27T00:00:00+00:00",
          "probability":0.4,"value":{"pending_task_count":5,"density_band":"HIGH"},
          "confidence":0.6,"data_quality":"partial","estimator_version":"deterministic-forecast-v1",
          "input_digest":"d","as_of":"2026-09-20T00:00:00+00:00","valid_until":"2026-09-21T00:00:00+00:00",
          "explanation_codes":["high_pending_density"],"evidence_summary":{},
          "limitations":["baseline_estimator_only","no_causal_claim"]}],"total":1,"page":1,
         "page_size":10,"has_more":false}
        """.trimIndent()
        val forecast = moshi.adapter(ForecastPageDto::class.java).fromJson(json)!!.items.single()
        assertEquals("UPCOMING_WORKLOAD", forecast.forecastType)
        assertEquals(0.4, forecast.probability!!, 1e-9)
        assertEquals(listOf("baseline_estimator_only", "no_causal_claim"), forecast.limitations)
    }

    @Test
    fun `intervention outcome parses persisted decision and status`() {
        val json = """
        {"evaluation_id":"inteval_1","intervention_id":"intv_1","goal_id":"plan:plan_1",
         "plan_id":"plan_1","as_of":"2026-09-27T00:00:00+00:00","observation_status":"COMPLETE",
         "execution_signal":"NOT_STARTED","adoption":"NOT_STARTED","plan_fidelity":"MATCHED",
         "verdict":"INCONCLUSIVE","observed_outcome":"DECLINED","causal_claim":"NOT_ESTIMATED",
         "state_comparison":{"delta":{"consistency":-0.5}},
         "decision":"REPLAN","decision_reason_codes":["state_declined"],
         "suggested_adjustments":["reduce_workload"],"decision_confidence":0.7,
         "decision_status":"APPLIED","lineage":{"supersedes_intervention_id":null,
          "superseded_by_intervention_id":"intv_2"},"observation_due_at":"2026-09-27T00:00:00+00:00",
         "warning_codes":[],"confidence":0.55,"data_quality":"partial","evaluator_version":"v1",
         "created_at":"2026-09-20T00:00:00+00:00"}
        """.trimIndent()
        val outcome = moshi.adapter(AdaptiveInterventionOutcomeDto::class.java).fromJson(json)!!
        assertEquals("DECLINED", outcome.observedOutcome)
        assertEquals("REPLAN", outcome.decision)
        assertEquals("APPLIED", outcome.decisionStatus)
        assertEquals(listOf("state_declined"), outcome.decisionReasonCodes)
    }

    @Test
    fun `data source controls and transparency parse`() {
        val controls = moshi.adapter(DataSourceControlListDto::class.java).fromJson(
            """{"items":[{"source_key":"CHAOXING","status":"PAUSED",
                 "updated_at":"2026-09-20T00:00:00+00:00","can_pause":false,"can_resume":true}]}""",
        )!!
        assertEquals("CHAOXING", controls.items.single().sourceKey)
        assertTrue(controls.items.single().canResume)

        val transparency = moshi.adapter(ModelTransparencyDto::class.java).fromJson(
            """{"capabilities":[{"capability_name":"learning_summary_v1","capability_version":"v1",
                 "production_method":"evidence_grounded_summary","campusmate_lm_status":"SHADOW_ONLY",
                 "quality_gate_passed":false,"performance_gate_passed":false,"performance_measured":false,
                 "uses_real_model_inference":false,"uses_fixed_prediction_file":true}],
                "campusmate_lm_enabled":false,"campusmate_lm_affects_production":false,
                "shadow_results_modify_plans":false,"read_only_canary_active":false,
                "uses_real_model_inference":false,"uses_fixed_prediction_file":true,
                "real_inference_observed":false,"fixture_only":false}""",
        )!!
        assertFalse(transparency.campusmateLmAffectsProduction)
        assertFalse(transparency.realInferenceObserved)
        assertEquals("SHADOW_ONLY", transparency.capabilities.single().campusmateLmStatus)
    }
}
