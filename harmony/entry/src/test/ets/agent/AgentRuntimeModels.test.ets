import { describe, expect, it } from '@ohos/hypium';
import {
  AgentDtoParser, AgentEnumParser,
  RunStatus, RunPhase, RiskLevel, AgentEventType, ApprovalStatus,
  ArtifactType, AgentErrorCode, AcademicPolicy, AssistanceMode,
  CitationVerification, NoticeWorkflowStatus, NoticeActionStatus,
  AdjustmentProposalStatus, PlanVersionStatus
} from '../../../main/ets/data/AgentRuntimeModels';

interface MockProgress {
  current: number;
  total: number;
  percent: number;
}

interface MockEventRaw {
  id: string;
  type: string;
  run_id: string;
  sequence: number;
  status: string;
  phase: string;
  role: string;
  summary: string;
  progress: MockProgress;
  artifact_id: string | null;
  approval_id: string | null;
  created_at: string;
}

interface MockRunRaw {
  run_id: string;
  job_id: string;
  user_id: string;
  status: string;
  phase: string;
  risk_level: string;
  started_at: string;
  finished_at: string;
  created_at: string;
  updated_at: string;
  error: string | null;
  artifact_ids: string[];
}

interface MockArtifactRaw {
  artifact_id: string;
  run_id: string;
  user_id: string;
  artifact_type: string;
  version: number;
  mime_type: string;
  size_bytes: number;
  content_hash: string;
  download_url: string;
  created_at: string;
}

interface MockSourcePolicy {
  course_material_priority: boolean;
  allow_web: boolean;
  allow_user_upload: boolean;
}

interface MockCourseResearchRaw {
  run_id: string;
  user_id: string;
  question: string;
  course_id: string;
  assistance_mode: string;
  academic_policy: string;
  source_policy: MockSourcePolicy;
  status: string;
  created_at: string;
  updated_at: string;
  artifact_ids: string[];
}

interface MockActionRaw {
  action_id: string;
  workflow_id: string;
  title: string;
  action_type: string;
  risk_level: string;
  status: string;
  external_ref: string;
}

interface MockNoticeWorkflowRaw {
  workflow_id: string;
  user_id: string;
  source_id: string;
  notice_id: string;
  status: string;
  confidence: number;
  uncertainty: string[];
  materials: string[];
  steps: string[];
  source_evidence: string[];
  actions: MockActionRaw[];
  created_at: string;
  updated_at: string;
}

interface MockErrorDetails {
  run_id: string;
  approval_id: string;
}

interface MockErrorEnvelopeRaw {
  code: string;
  message: string;
  request_id: string;
  details: MockErrorDetails;
}

interface MockUnknownErrorRaw {
  code: string;
  message: string;
  request_id: string;
}

interface MockJobInputRef {
  goal_id: string;
}

interface MockJobRaw {
  job_id: string;
  user_id: string;
  job_kind: string;
  status: string;
  created_at: string;
  updated_at: string;
  latest_run_id: string;
  input_ref: MockJobInputRef;
}

interface MockApprovalRaw {
  approval_id: string;
  run_id: string;
  status: string;
  risk_level: string;
  action_summary: string;
  expires_at: string;
  resolved_at: string | null;
  decision_reason: string | null;
}

export default function agentRuntimeModelsTest(): void {
  describe('AgentRuntimeModels', () => {
    it('parses runtime fixture event with known enums', 0, () => {
      const raw: MockEventRaw = {
        id: 'evt_10018', type: 'TOOL_COMPLETED', run_id: 'run_01H8XKQD2',
        sequence: 18, status: 'RUNNING', phase: 'WAITING_FOR_TOOL',
        role: 'planner', summary: '已完成课程信息查询',
        progress: { current: 3, total: 7, percent: 42 },
        artifact_id: null, approval_id: null,
        created_at: '2026-09-12T10:05:00+08:00'
      };
      const event = AgentDtoParser.event(raw as Object as Record<string, Object>);
      expect(event.id).assertEqual('evt_10018');
      expect(event.type).assertEqual(AgentEventType.TOOL_COMPLETED);
      expect(event.status).assertEqual(RunStatus.RUNNING);
      expect(event.phase).assertEqual(RunPhase.WAITING_FOR_TOOL);
      const progress = event.progress;
      expect(progress !== null ? progress.current : 0).assertEqual(3);
      expect(progress !== null ? progress.percent : 0).assertEqual(42);
    });

    it('parses final_review fixture run and artifact', 0, () => {
      const runRaw: MockRunRaw = {
        run_id: 'run_fr_001', job_id: 'job_fr_001', user_id: 'user_demo_001',
        status: 'SUCCEEDED', phase: 'IDLE', risk_level: 'CONFIRM_REQUIRED',
        started_at: '2026-09-12T10:00:01+08:00', finished_at: '2026-09-12T10:20:00+08:00',
        created_at: '2026-09-12T10:00:00+08:00', updated_at: '2026-09-12T10:20:00+08:00',
        error: null, artifact_ids: ['art_fr+fr_plan_v1']
      };
      const run = AgentDtoParser.run(runRaw as Object as Record<string, Object>);
      expect(run.run_id).assertEqual('run_fr_001');
      expect(run.status).assertEqual(RunStatus.SUCCEEDED);
      expect(run.risk_level).assertEqual(RiskLevel.CONFIRM_REQUIRED);
      expect(run.artifact_ids.length).assertEqual(1);

      const artRaw: MockArtifactRaw = {
        artifact_id: 'art_fr_plan_v1', run_id: 'run_fr_001', user_id: 'user_demo_001',
        artifact_type: 'FINAL_REVIEW_PLAN', version: 1, mime_type: 'application/json',
        size_bytes: 4096, content_hash: 'sha256:final_review_v1_hash',
        download_url: '/api/v1/agent-artifacts/art_fr_plan_v1/content',
        created_at: '2026-09-12T10:20:00+08:00'
      };
      const art = AgentDtoParser.artifact(artRaw as Object as Record<string, Object>);
      expect(art.artifact_type).assertEqual(ArtifactType.FINAL_REVIEW_PLAN);
      expect(art.version).assertEqual(1);
      expect(art.download_url.endsWith('/content')).assertEqual(true);
    });

    it('parses course_research fixture with policy fields', 0, () => {
      const raw: MockCourseResearchRaw = {
        run_id: 'run_cr_001', user_id: 'user_demo_001',
        question: '解释快速排序', course_id: 'course_x',
        assistance_mode: 'EXPLAIN', academic_policy: 'LIMITED',
        source_policy: { course_material_priority: true, allow_web: true, allow_user_upload: true },
        status: 'PARTIAL', created_at: '2026-09-12T11:00:00+08:00',
        updated_at: '2026-09-12T11:15:00+08:00', artifact_ids: ['art_cr_report']
      };
      const run = AgentDtoParser.courseResearchRun(raw as Object as Record<string, Object>);
      expect(run.assistance_mode).assertEqual(AssistanceMode.EXPLAIN);
      expect(run.academic_policy).assertEqual(AcademicPolicy.LIMITED);
      expect(run.source_policy.allow_web).assertEqual(true);
      expect(run.status).assertEqual(RunStatus.PARTIAL);
    });

    it('parses notice_workflow fixture with uncertainty and actions', 0, () => {
      const actions: MockActionRaw[] = [{
        action_id: 'act_001', workflow_id: 'wf_001', title: '提交作业',
        action_type: 'external_submit', risk_level: 'MANUAL_ONLY', status: 'PROPOSED', external_ref: 'portal'
      }];
      const raw: MockNoticeWorkflowRaw = {
        workflow_id: 'wf_001', user_id: 'user_demo_001', source_id: 'src_manual',
        notice_id: 'notice_1', status: 'WAITING_CONFIRMATION', confidence: 0.6,
        uncertainty: ['deadline'], materials: ['实验报告.pdf'], steps: [], source_evidence: [],
        actions: actions,
        created_at: '2026-09-12T12:00:00+08:00', updated_at: '2026-09-12T12:05:00+08:00'
      };
      const wf = AgentDtoParser.noticeWorkflow(raw as Object as Record<string, Object>);
      expect(wf.status).assertEqual(NoticeWorkflowStatus.WAITING_CONFIRMATION);
      expect(wf.uncertainty.missing_fields[0]).assertEqual('deadline');
      expect(wf.actions[0].risk_level).assertEqual(RiskLevel.MANUAL_ONLY);
      expect(wf.actions[0].is_external).assertEqual(true);
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
      const raw: MockErrorEnvelopeRaw = {
        code: 'AGENT_APPROVAL_REQUIRED', message: '需要用户确认后继续',
        request_id: 'req_01H8XKQD0',
        details: { run_id: 'run_01H8XKQD2', approval_id: 'apv_01H8XKQD4' }
      };
      const env = AgentDtoParser.errorEnvelope(raw as Object as Record<string, Object>);
      expect(env.code).assertEqual(AgentErrorCode.AGENT_APPROVAL_REQUIRED);
      expect(env.request_id).assertEqual('req_01H8XKQD0');
      const details = env.details;
      expect(details !== undefined ? details.run_id : '').assertEqual('run_01H8XKQD2');
    });

    it('parses error envelope with unknown code safely', 0, () => {
      const raw: MockUnknownErrorRaw = {
        code: 'AGENT_UNIVERSE_COLLAPSE', message: '未知错误',
        request_id: 'req_x'
      };
      const env = AgentDtoParser.errorEnvelope(raw as Object as Record<string, Object>);
      expect(env.code).assertEqual(AgentErrorCode.UNKNOWN);
    });

    it('parses approval with nullable resolved fields', 0, () => {
      const raw: MockApprovalRaw = {
        approval_id: 'apv_nw_001', run_id: 'run_nw_001', status: 'PENDING',
        risk_level: 'MANUAL_ONLY', action_summary: '在教务系统手动提交作业',
        expires_at: '2026-09-12T12:35:00+08:00', resolved_at: null, decision_reason: null
      };
      const approval = AgentDtoParser.approval(raw as Object as Record<string, Object>);
      expect(approval.status).assertEqual(ApprovalStatus.PENDING);
      expect(approval.risk_level).assertEqual(RiskLevel.MANUAL_ONLY);
      expect(approval.resolved_at).assertEqual(null);
    });

    // ===== Agent Runtime v2 增量契约 =====
    // 与 backend/tests/fixtures/agent_runtime/v1/runtime.json 的 v2 段保持一致:
    // 恢复事件与 v2 错误码必须可解析;未知值安全降级到 UNKNOWN,不崩溃、不提升权限。

    it('recognises v2 recovery event types', 0, () => {
      const recovery: string[] = ['RUN_RETRY_SCHEDULED', 'RUN_RECOVERY_STARTED', 'RUN_RECOVERED'];
      recovery.forEach((raw: string) => {
        expect(AgentEnumParser.eventType(raw) !== AgentEventType.UNKNOWN).assertTrue();
      });
    });

    it('recognises v2 error codes', 0, () => {
      const codes: string[] = [
        'AGENT_CAPABILITY_DISABLED', 'AGENT_RUNTIME_UNAVAILABLE',
        'AGENT_CURSOR_INVALID', 'AGENT_IDEMPOTENCY_CONFLICT'
      ];
      codes.forEach((rawCode: string) => {
        const raw: MockUnknownErrorRaw = { code: rawCode, message: 'x', request_id: 'req_x' };
        const env = AgentDtoParser.errorEnvelope(raw as Object as Record<string, Object>);
        expect(env.code !== AgentErrorCode.UNKNOWN).assertTrue();
      });
    });

    it('202 creation without plan id is a queued job, not a failure', 0, () => {
      const raw: MockJobRaw = {
        job_id: 'job_01H8XKQD9', user_id: 'user_demo_001', job_kind: 'learning_goal',
        status: 'QUEUED', created_at: 't', updated_at: 't',
        latest_run_id: 'run_01H8XKQDA', input_ref: { goal_id: 'goal_demo_001' }
      };
      const job = AgentDtoParser.job(raw as Object as Record<string, Object>);
      expect(job.status).assertEqual(RunStatus.QUEUED);
      expect(job.latest_run_id !== null).assertTrue();
      expect(job.input_ref['plan_id'] === undefined).assertTrue();
    });
  });
}
