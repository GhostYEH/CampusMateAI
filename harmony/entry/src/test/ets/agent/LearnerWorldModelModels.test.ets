import { describe, expect, it } from '@ohos/hypium';
import { AgentDtoParser } from '../../../main/ets/data/AgentRuntimeModels';

/**
 * 世界模型解析器契约测试。
 *
 * 用**后端真实返回形状**验证：
 * 1. 页面需要的字段能解析出来；
 * 2. 未建模的自由结构（`value` / `state_comparison`）不会导致解析失败；
 * 3. 降级标记（`data_quality` / `warning_codes` / `limitations`）不会丢；
 * 4. 候选注解在不可用时只带稳定 reason，不带任何候选文本。
 */
export default function learnerWorldModelModelsTest(): void {
  describe('LearnerWorldModelModels', () => {
    it('parses candidate annotation with read-only flags', 0, () => {
      const raw: Record<string, Object> = {
        'plan_id': 'plan_1',
        'status': 'PROPOSED',
        'stage': 'AWAITING_CONFIRMATION',
        'headline': '计划草案已生成，等待学生确认',
        'completion_percent': 0,
        'planned_item_count': 2,
        'executed_item_count': 0,
        'planned_minutes': 60,
        'next_action': '确认计划后创建个人待办',
        'recommendations': [] as string[],
        'warning_codes': ['data_quality_partial'] as string[],
        'generated_at': '2026-09-20T10:00:00+00:00',
        'candidate_annotation': {
          'available': true,
          'capability_name': 'learning_summary_v1',
          'capability_version': 'v1',
          'reason': null,
          'inference_source': 'REAL_MODEL',
          'model_key': 'campusmate-lm',
          'prompt_version': 'learning_summary_v1-prompt-v1',
          'shadow_run_id': 'shadow_1',
          'used_fallback': false,
          'claim_codes': ['PRIORITIZE_NEAR_DEADLINE'] as string[],
          'summary': '建议按已提供的优先级安排短时学习。',
          'read_only': true,
          'affects_production': false
        } as Record<string, Object>
      };
      const summary = AgentDtoParser.learningPlanSummary(raw);
      expect(summary.plan_id).assertEqual('plan_1');
      expect(summary.warning_codes.length).assertEqual(1);
      expect(summary.candidate_annotation !== null).assertTrue();
      if (summary.candidate_annotation !== null) {
        expect(summary.candidate_annotation.available).assertTrue();
        expect(summary.candidate_annotation.inference_source).assertEqual('REAL_MODEL');
        expect(summary.candidate_annotation.shadow_run_id).assertEqual('shadow_1');
        expect(summary.candidate_annotation.read_only).assertTrue();
        expect(summary.candidate_annotation.affects_production).assertFalse();
      }
    });

    it('keeps degraded candidate annotation free of candidate text', 0, () => {
      const annotation = AgentDtoParser.candidateAnnotation({
        'available': false,
        'capability_name': 'learning_summary_v1',
        'capability_version': 'v1',
        'reason': 'MODEL_TIMEOUT',
        'inference_source': 'DETERMINISTIC_FALLBACK',
        'model_key': null,
        'prompt_version': null,
        'shadow_run_id': null,
        'used_fallback': true,
        'claim_codes': [] as string[],
        'summary': null,
        'read_only': true,
        'affects_production': false
      } as Record<string, Object>);
      expect(annotation !== null).assertTrue();
      if (annotation !== null) {
        expect(annotation.available).assertFalse();
        expect(annotation.reason).assertEqual('MODEL_TIMEOUT');
        expect(annotation.used_fallback).assertTrue();
        expect(annotation.summary).assertNull();
        expect(annotation.claim_codes.length).assertEqual(0);
      }
    });

    it('returns null for a missing or malformed candidate annotation', 0, () => {
      expect(AgentDtoParser.candidateAnnotation(undefined)).assertNull();
      expect(AgentDtoParser.candidateAnnotation(null)).assertNull();
      expect(AgentDtoParser.candidateAnnotation('not-an-object')).assertNull();
    });

    it('parses snapshot page and keeps data quality warnings', 0, () => {
      const page = AgentDtoParser.learnerStateSnapshotPage({
        'items': [{
          'snapshot_id': 'lsnap_1',
          'state_type': 'task_workload',
          'value': { 'pending_task_count': 3 } as Record<string, Object>,
          'confidence': 0.6,
          'data_quality': 'partial',
          'projection_kind': 'CORE',
          'warning_codes': ['learner_data_source_paused'] as string[],
          'evidence_count': 2
        } as Record<string, Object>],
        'total': 1
      } as Record<string, Object>);
      expect(page.total).assertEqual(1);
      expect(page.items.length).assertEqual(1);
      expect(page.items[0].state_type).assertEqual('task_workload');
      expect(page.items[0].data_quality).assertEqual('partial');
      expect(page.items[0].warning_codes.length).assertEqual(1);
      expect(page.items[0].evidence_count).assertEqual(2);
    });

    it('parses forecast summary and tolerates the polymorphic value', 0, () => {
      const forecast = AgentDtoParser.forecastSummary({
        'forecast_id': 'fc_1',
        'forecast_type': 'UPCOMING_WORKLOAD',
        'probability': 0.4,
        'value': { 'density_band': 'HIGH' } as Record<string, Object>,
        'confidence': 0.6,
        'data_quality': 'partial',
        'horizon_end': '2026-09-27T00:00:00+00:00',
        'explanation_codes': ['high_pending_density'] as string[],
        'limitations': ['baseline_estimator_only', 'no_causal_claim'] as string[]
      } as Record<string, Object>);
      expect(forecast.forecast_type).assertEqual('UPCOMING_WORKLOAD');
      expect(forecast.probability).assertEqual(0.4);
      expect(forecast.limitations.length).assertEqual(2);
    });

    it('parses persisted intervention decision and status', 0, () => {
      const outcome = AgentDtoParser.adaptiveInterventionOutcome({
        'intervention_id': 'intv_1',
        'plan_id': 'plan_1',
        'observation_status': 'COMPLETE',
        'execution_signal': 'NOT_STARTED',
        'adoption': 'NOT_STARTED',
        'verdict': 'INCONCLUSIVE',
        'observed_outcome': 'DECLINED',
        'causal_claim': 'NOT_ESTIMATED',
        'state_comparison': { 'delta': { 'consistency': -0.5 } } as Record<string, Object>,
        'decision': 'REPLAN',
        'decision_reason_codes': ['state_declined'] as string[],
        'suggested_adjustments': ['reduce_workload'] as string[],
        'decision_status': 'APPLIED',
        'scope_type': 'PLAN',
        'observation_due_at': '2026-09-27T00:00:00+00:00',
        'warning_codes': [] as string[]
      } as Record<string, Object>);
      expect(outcome.observed_outcome).assertEqual('DECLINED');
      expect(outcome.decision).assertEqual('REPLAN');
      expect(outcome.decision_status).assertEqual('APPLIED');
      expect(outcome.scope_type).assertEqual('PLAN');
      expect(outcome.decision_reason_codes.length).assertEqual(1);
    });

    it('parses data source controls and model transparency honestly', 0, () => {
      const control = AgentDtoParser.dataSourceControl({
        'source_key': 'CHAOXING',
        'status': 'PAUSED',
        'can_pause': false,
        'can_resume': true
      } as Record<string, Object>);
      expect(control.source_key).assertEqual('CHAOXING');
      expect(control.can_resume).assertTrue();

      const transparency = AgentDtoParser.modelTransparency({
        'capabilities': [{
          'capability_name': 'learning_summary_v1',
          'campusmate_lm_status': 'SHADOW_ONLY',
          'quality_gate_passed': false,
          'performance_measured': false,
          'uses_real_model_inference': false
        } as Record<string, Object>],
        'campusmate_lm_enabled': false,
        'campusmate_lm_affects_production': false,
        'shadow_results_modify_plans': false,
        'read_only_canary_active': false,
        'real_inference_observed': false,
        'fixture_only': false
      } as Record<string, Object>);
      expect(transparency.campusmate_lm_affects_production).assertFalse();
      expect(transparency.real_inference_observed).assertFalse();
      expect(transparency.capabilities.length).assertEqual(1);
      expect(transparency.capabilities[0].campusmate_lm_status).assertEqual('SHADOW_ONLY');
    });
  });
}
