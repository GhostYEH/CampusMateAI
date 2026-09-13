import { describe, expect, it } from '@ohos/hypium';
import { AgentEventReducer, IdempotencyKey, AgentRunView } from '../../../main/ets/service/AgentEventReducer';
import {
  AgentEvent, AgentEventType, RunStatus, RunPhase, RiskLevel, AgentApproval, ApprovalStatus,
  AgentDtoParser, FinalReviewCampaign, FinalReviewPlanVersion
} from '../../../main/ets/data/AgentRuntimeModels';

interface MockCampaignRaw {
  campaign_id: string;
  user_id: string;
  exam_ids: string[];
  daily_capacity_minutes: number;
  preferred_periods: string[];
  rest_days: string[];
  intensity: string;
  status: string;
  active_version: number;
  created_at: string;
  updated_at: string;
}

interface MockPlanItem {
  topic: string;
}

interface MockPlanDay {
  date: string;
  items: MockPlanItem[];
}

interface MockPlanContent {
  days: MockPlanDay[];
}

interface MockEmptyPlan {}

interface MockPlanVersionRaw {
  campaign_id: string;
  version: number;
  plan: MockPlanContent | MockEmptyPlan;
  model_provider: string;
  route_policy: string;
  risk_level: string;
  approval_id: string;
  supersedes_version: number | null;
  created_at: string;
}

function evt(id: string, seq: number, type: AgentEventType, status: RunStatus,
  phase: RunPhase, summary: string, approvalId: string | null, artifactId: string | null): AgentEvent {
  return {
    id: id, type: type, run_id: 'run_fr', sequence: seq, status: status, phase: phase,
    role: 'planner', summary: summary, progress: null,
    artifact_id: artifactId, approval_id: approvalId, created_at: '2026-09-12T10:00:00+08:00'
  };
}

export default function finalReviewStateTest(): void {
  describe('FinalReview golden flow', () => {
    it('create -> generate -> approve -> artifact -> complete produces succeeded view', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_fr');
      view = AgentEventReducer.append(view, evt('e1', 1, AgentEventType.RUN_STARTED, RunStatus.RUNNING, RunPhase.CONTEXT_BUILDING, '构建上下文', null, null));
      view = AgentEventReducer.append(view, evt('e10', 10, AgentEventType.MODEL_COMPLETED, RunStatus.RUNNING, RunPhase.VALIDATING_OUTPUT, 'Zhipu 生成计划提案', null, null));
      view = AgentEventReducer.append(view, evt('e20', 20, AgentEventType.APPROVAL_REQUIRED, RunStatus.AWAITING_APPROVAL, RunPhase.WAITING_FOR_APPROVAL, '需要用户确认', 'apv_fr', null));
      expect(view.pendingApprovalId).assertEqual('apv_fr');

      const approval: AgentApproval = {
        approval_id: 'apv_fr', run_id: 'run_fr', status: ApprovalStatus.APPROVED,
        risk_level: RiskLevel.CONFIRM_REQUIRED, action_summary: '激活计划 v1',
        expires_at: '2026-09-12T10:18:00+08:00', resolved_at: '2026-09-12T10:09:00+08:00',
        decision_reason: '用户确认'
      };
      view = AgentEventReducer.applyApproval(view, approval);
      expect(view.pendingApprovalId).assertEqual(null);

      view = AgentEventReducer.append(view, evt('e25', 25, AgentEventType.APPROVAL_RESOLVED, RunStatus.RUNNING, RunPhase.PERSISTING_RESULT, '计划 v1 已激活', 'apv_fr', null));
      view = AgentEventReducer.append(view, evt('e30', 30, AgentEventType.ARTIFACT_CREATED, RunStatus.SUCCEEDED, RunPhase.IDLE, '产物已生成', null, 'art_fr_plan_v1'));
      view = AgentEventReducer.append(view, evt('e40', 40, AgentEventType.RUN_COMPLETED, RunStatus.SUCCEEDED, RunPhase.IDLE, 'Run 已完成', null, null));

      expect(view.status).assertEqual(RunStatus.SUCCEEDED);
      expect(view.pendingApprovalId).assertEqual(null);
      expect(view.artifactId).assertEqual('art_fr_plan_v1');
      expect(view.partial).assertEqual(false);
      expect(view.failed).assertEqual(false);
    });

    it('uses stable Idempotency-Key across campaign create and plan generate', 0, () => {
      const createKey: string = IdempotencyKey.forCampaignCreate(['exam_1', 'exam_2']);
      const genKey: string = IdempotencyKey.forPlanGenerate('camp_fr');
      const activateKey: string = IdempotencyKey.forCampaignActivate('camp_fr', 1);
      expect(createKey).assertEqual('fr:campaign:create:exam_1,exam_2');
      expect(genKey).assertEqual('fr:plan:generate:camp_fr');
      expect(activateKey).assertEqual('fr:campaign:activate:camp_fr:1');
    });

    it('parses campaign and immutable plan version from fixture shape', 0, () => {
      const campaignRaw: MockCampaignRaw = {
        campaign_id: 'camp_fr', user_id: 'user_demo_001',
        exam_ids: ['exam_1', 'exam_2'], daily_capacity_minutes: 120,
        preferred_periods: [], rest_days: [], intensity: 'medium', status: 'active', active_version: 1,
        created_at: '2026-09-12T10:00:00+08:00', updated_at: '2026-09-12T10:20:00+08:00'
      };
      const campaign: FinalReviewCampaign = AgentDtoParser.finalReviewCampaign(campaignRaw as Object as Record<string, Object>);
      expect(campaign.exam_ids.length).assertEqual(2);
      expect(campaign.daily_capacity_minutes).assertEqual(120);

      const planItem: MockPlanItem = { topic: '排序算法' };
      const planDay: MockPlanDay = { date: '2026-09-13', items: [planItem] };
      const planContent: MockPlanContent = { days: [planDay] };
      const versionRaw: MockPlanVersionRaw = {
        campaign_id: 'camp_fr', version: 1,
        plan: planContent,
        model_provider: 'zhipu', route_policy: 'reasoning_primary',
        risk_level: 'CONFIRM_REQUIRED', approval_id: 'apv_fr', supersedes_version: null,
        created_at: '2026-09-12T10:15:00+08:00'
      };
      const version: FinalReviewPlanVersion = AgentDtoParser.finalReviewPlanVersion(versionRaw as Object as Record<string, Object>);
      expect(version.risk_level).assertEqual(RiskLevel.CONFIRM_REQUIRED);
      expect(version.model_provider).assertEqual('zhipu');
      expect(version.approval_id).assertEqual('apv_fr');
    });

    it('keeps v1 readable after v2 is activated (immutable versions)', 0, () => {
      const emptyPlan: MockEmptyPlan = {};
      const v1Raw: MockPlanVersionRaw = {
        campaign_id: 'camp_fr', version: 1, plan: emptyPlan, model_provider: 'zhipu',
        route_policy: 'reasoning_primary', risk_level: 'CONFIRM_REQUIRED', approval_id: 'a1',
        supersedes_version: null, created_at: '2026-09-12T10:15:00+08:00'
      };
      const v2Raw: MockPlanVersionRaw = {
        campaign_id: 'camp_fr', version: 2, plan: emptyPlan, model_provider: 'zhipu',
        route_policy: 'reasoning_primary', risk_level: 'CONFIRM_REQUIRED', approval_id: 'a2',
        supersedes_version: 1, created_at: '2026-09-13T10:00:00+08:00'
      };
      const v1: FinalReviewPlanVersion = AgentDtoParser.finalReviewPlanVersion(v1Raw as Object as Record<string, Object>);
      const v2: FinalReviewPlanVersion = AgentDtoParser.finalReviewPlanVersion(v2Raw as Object as Record<string, Object>);
      expect(v1.version).assertEqual(1);
      expect(v2.version).assertEqual(2);
      expect(v2.supersedes_version).assertEqual(1);
    });
  });
}
