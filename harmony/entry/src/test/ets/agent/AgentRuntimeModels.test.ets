import { describe, expect, it } from '@ohos/hypium';
import {
  AgentDtoParser, AgentEnumParser,
  RunStatus, RunPhase, RiskLevel, AgentEventType, ApprovalStatus,
  ArtifactType, AgentErrorCode, AcademicPolicy, AssistanceMode,
  CitationVerification, NoticeWorkflowStatus, NoticeActionStatus,
  AdjustmentProposalStatus, PlanVersionStatus
} from '../../../main/ets/data/AgentRuntimeModels';

export default function agentRuntimeModelsTest(): void {
  describe('AgentRuntimeModels', () => {
    it('parses runtime fixture event with known enums', 0, () => {
      const raw: Record<string, Object> = {
        id: 'evt_10018', type: 'TOOL_COMPLETED', run_id: 'run_01H8XKQD2',
        sequence: 18, status: 'RUNNING', phase: 'WAITING_FOR_TOOL',
        role: 'planner', summary: '已完成课程信息查询',
        progress: { current: 3, total: 7, percent: 42 },
        artifact_id: null, approval_id: null,
        created_at: '2026-09-12T10:05:00+08:00'
      };
      const event = AgentDtoParser.event(raw);
      expect(event.id).assertEqual('evt_10018');
      expect(event.type).assertEqual(AgentEventType.TOOL_COMPLETED);
      expect(event.status).assertEqual(RunStatus.RUNNING);
      expect(event.phase).assertEqual(RunPhase.WAITING_FOR_TOOL);
      expect(event.progress.current).assertEqual(3);
      expect(event.progress.percent).assertEqual(42);
    });

    it('parses final_review fixture run and artifact', 0, () => {
      const runRaw: Record<string, Object> = {
        run_id: 'run_fr_001', job_id: 'job_fr_001', user_id: 'user_demo_001',
        status: 'SUCCEEDED', phase: 'IDLE', risk_level: 'CONFIRM_REQUIRED',
        started_at: '2026-09-12T10:00:01+08:00', finished_at: '2026-09-12T10:20:00+08:00',
        created_at: '2026-09-12T10:00:00+08:00', updated_at: '2026-09-12T10:20:00+08:00',
        error: null, artifact_ids: ['art_fr+fr_plan_v1']
      };
      const run = AgentDtoParser.run(runRaw);
      expect(run.run_id).assertEqual('run_fr_001');
      expect(run.status).assertEqual(RunStatus.SUCCEEDED);
      expect(run.risk_level).assertEqual(RiskLevel.CONFIRM_REQUIRED);
      expect(run.artifact_ids.length).assertEqual(1);

      const artRaw: Record<string, Object> = {
        artifact_id: 'art_fr_plan_v1', run_id: 'run_fr_001', user_id: 'user_demo_001',
        artifact_type: 'FINAL_REVIEW_PLAN', version: 1, mime_type: 'application/json',
        size_bytes: 4096, content_hash: 'sha256:final_review_v1_hash',
        download_url: '/api/v1/agent-artifacts/art_fr_plan_v1',
        created_at: '2026-09-12T10:20:00+08:00'
      };
      const art = AgentDtoParser.artifact(artRaw);
      expect(art.artifact_type).assertEqual(ArtifactType.FINAL_REVIEW_PLAN);
      expect(art.version).assertEqual(1);
    });

    it('parses course_research fixture with policy fields', 0, () => {
      const raw: Record<string, Object> = {
        run_id: 'run_cr_001', user_id: 'user_demo_001',
        question: '解释快速排序', course_id: 'course_x',
        assistance_mode: 'EXPLAIN', academic_policy: 'LIMITED',
        source_policy: { course_material_priority: true, allow_web: true, allow_user_upload: true },
        status: 'PARTIAL', created_at: '2026-09-12T11:00:00+08:00',
        updated_at: '2026-09-12T11:15:00+08:00', artifact_ids: ['art_cr_report']
      };
      const run = AgentDtoParser.courseResearchRun(raw);
      expect(run.assistance_mode).assertEqual(AssistanceMode.EXPLAIN);
      expect(run.academic_policy).assertEqual(AcademicPolicy.LIMITED);
      expect(run.source_policy.allow_web).assertEqual(true);
      expect(run.status).assertEqual(RunStatus.PARTIAL);
    });

    it('parses notice_workflow fixture with uncertainty and actions', 0, () => {
      const raw: Record<string, Object> = {
        workflow_id: 'wf_001', user_id: 'user_demo_001', source_id: 'src_manual',
        status: 'WAITING_CONFIRMATION',
        uncertainty: { missing_fields: ['deadline'], confidence: 'MEDIUM', notes: '截止时间不明确' },
        actions: [{
          action_id: 'act_001', workflow_id: 'wf_001', title: '提交作业',
          risk_level: 'MANUAL_ONLY', status: 'PROPOSED', materials: ['实验报告.pdf'], is_external: true
        }],
        created_at: '2026-09-12T12:00:00+08:00', updated_at: '2026-09-12T12:05:00+08:00'
      };
      const wf = AgentDtoParser.noticeWorkflow(raw);
      expect(wf.status).assertEqual(NoticeWorkflowStatus.WAITING_CONFIRMATION);
      expect(wf.uncertainty.missing_fields[0]).assertEqual('deadline');
      expect(wf.actions[0].risk_level).assertEqual(RiskLevel.MANUAL_ONLY);
      expect(wf.actions[0].is_external).assertEqual(true);
      expect(wf.actions[0].materials[0]).assertEqual('实验报告.pdf');
    });

    it('falls back to UNKNOWN for unrecognized enum values', 0, () => {
      expect(AgentEnumParser.runStatus('FROZEN')).assertEqual(RunStatus.UNKNOWN);
      expect(AgentEnumParser.runPhase('COOKING')).assertEqual(RunPhase.UNKNOWN);
      expect(AgentEnumParser.riskLevel('EXTREME')).assertEqual(RiskLevel.UNKNOWN);
      expect(AgentEnumParser.eventType('NUKE_STARTED')).assertEqual(AgentEventType.UNKNOWN);
      expect(AgentEnumParser.approvalStatus('REVOKED')).assertEqual(ApprovalStatus.UNKNOWN);
      expect(AgentEnumParser.artifactType('UFO_REPORT')).assertEqual(ArtifactType.UNKNOWN);
      expect(AgentEnumParser.errorCode('AGENT_ALIEN_INVASION')).assertEqual(AgentErrorCode.UNKNOWN);
      expect(AgentEnumParser.academicPolicy('BANNED')).assertEqual(AcademicPolicy.UNKNOWN);
      expect(AgentEnumParser.assistanceMode('TELEPATHY')).assertEqual(AssistanceMode.UNKNOWN);
      expect(AgentEnumParser.citationVerification('GUESSED')).assertEqual(CitationVerification.UNKNOWN);
      expect(AgentEnumParser.noticeWorkflowStatus('ARCHIVED')).assertEqual(NoticeWorkflowStatus.UNKNOWN);
      expect(AgentEnumParser.noticeActionStatus('SKIPPED')).assertEqual(NoticeActionStatus.UNKNOWN);
      expect(AgentEnumParser.planVersionStatus('DELETED')).assertEqual(PlanVersionStatus.UNKNOWN);
      expect(AgentEnumParser.adjustmentProposalStatus('CANCELLED')).assertEqual(AdjustmentProposalStatus.UNKNOWN);
    });

    it('parses error envelope with stable code', 0, () => {
      const raw: Record<string, Object> = {
        code: 'AGENT_APPROVAL_REQUIRED', message: '需要用户确认后继续',
        request_id: 'req_01H8XKQD0',
        details: { run_id: 'run_01H8XKQD2', approval_id: 'apv_01H8XKQD4' }
      };
      const env = AgentDtoParser.errorEnvelope(raw);
      expect(env.code).assertEqual(AgentErrorCode.AGENT_APPROVAL_REQUIRED);
      expect(env.request_id).assertEqual('req_01H8XKQD0');
      expect(env.details.run_id).assertEqual('run_01H8XKQD2');
    });

    it('parses error envelope with unknown code safely', 0, () => {
      const raw: Record<string, Object> = {
        code: 'AGENT_UNIVERSE_COLLAPSE', message: '未知错误',
        request_id: 'req_x'
      };
      const env = AgentDtoParser.errorEnvelope(raw);
      expect(env.code).assertEqual(AgentErrorCode.UNKNOWN);
    });

    it('parses approval with nullable resolved fields', 0, () => {
      const raw: Record<string, Object> = {
        approval_id: 'apv_nw_001', run_id: 'run_nw_001', status: 'PENDING',
        risk_level: 'MANUAL_ONLY', action_summary: '在教务系统手动提交作业',
        expires_at: '2026-09-12T12:35:00+08:00', resolved_at: null, decision_reason: null
      };
      const approval = AgentDtoParser.approval(raw);
      expect(approval.status).assertEqual(ApprovalStatus.PENDING);
      expect(approval.risk_level).assertEqual(RiskLevel.MANUAL_ONLY);
      expect(approval.resolved_at).assertEqual(null);
    });
  });
}