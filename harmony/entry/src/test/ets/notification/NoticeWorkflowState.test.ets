import { describe, expect, it } from '@ohos/hypium';
import { AgentEventReducer, IdempotencyKey, AgentRunView } from '../../../main/ets/service/AgentEventReducer';
import {
  AgentEvent, AgentEventType, RunStatus, RunPhase, RiskLevel, AgentApproval, ApprovalStatus,
  AgentDtoParser, NoticeWorkflow, NoticeWorkflowStatus, NoticeWorkflowAction, NoticeActionStatus,
  NoticeUncertainty
} from '../../../main/ets/data/AgentRuntimeModels';

interface MockActionRaw {
  action_id: string;
  workflow_id: string;
  title: string;
  action_type: string;
  risk_level: string;
  status: string;
  external_ref: string | null;
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

function evt(id: string, seq: number, type: AgentEventType, status: RunStatus,
  phase: RunPhase, role: string, summary: string, approvalId: string | null): AgentEvent {
  return {
    id: id, type: type, run_id: 'run_nw', sequence: seq, status: status, phase: phase,
    role: role, summary: summary, progress: null,
    artifact_id: null, approval_id: approvalId, created_at: '2026-09-12T12:00:00+08:00'
  };
}

export default function noticeWorkflowStateTest(): void {
  describe('NoticeWorkflow golden flow', () => {
    it('paste -> interpret -> AUTO_SAFE task -> MANUAL_ONLY approval stays pending', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_nw');
      view = AgentEventReducer.append(view, evt('e1', 1, AgentEventType.RUN_STARTED, RunStatus.RUNNING, RunPhase.CONTEXT_BUILDING, 'notice_interpreter', '解析通知文本', null));
      view = AgentEventReducer.append(view, evt('e10', 10, AgentEventType.TOOL_COMPLETED, RunStatus.RUNNING, RunPhase.WAITING_FOR_TOOL, 'workflow_planner', '已创建个人待办(AUTO_SAFE)', null));
      view = AgentEventReducer.append(view, evt('e20', 20, AgentEventType.APPROVAL_REQUIRED, RunStatus.AWAITING_APPROVAL, RunPhase.WAITING_FOR_APPROVAL, 'workflow_planner', '外部提交动作需用户手动完成', 'apv_nw'));

      expect(view.status).assertEqual(RunStatus.AWAITING_APPROVAL);
      expect(view.pendingApprovalId).assertEqual('apv_nw');
    });

    it('does not auto-execute MANUAL_ONLY actions (conservative gate)', 0, () => {
      const actionRaw: MockActionRaw = {
        action_id: 'act_manual', workflow_id: 'wf_1', title: '在教务系统手动提交作业',
        action_type: 'external_submit', risk_level: 'MANUAL_ONLY', status: 'PROPOSED', external_ref: 'portal'
      };
      const manualAction: NoticeWorkflowAction = AgentDtoParser.noticeWorkflowAction(actionRaw as Object as Record<string, Object>);
      expect(AgentEventReducer.isManualOnly(manualAction.risk_level)).assertEqual(true);
      expect(manualAction.is_external).assertEqual(true);
    });

    it('allows AUTO_SAFE actions to proceed without approval', 0, () => {
      const actionRaw: MockActionRaw = {
        action_id: 'act_auto', workflow_id: 'wf_1', title: '创建个人待办',
        action_type: 'task.create', risk_level: 'AUTO_SAFE', status: 'DONE', external_ref: null
      };
      const autoAction: NoticeWorkflowAction = AgentDtoParser.noticeWorkflowAction(actionRaw as Object as Record<string, Object>);
      expect(AgentEventReducer.isManualOnly(autoAction.risk_level)).assertEqual(false);
      expect(autoAction.status).assertEqual(NoticeActionStatus.DONE);
    });

    it('parses workflow uncertainty from fixture shape', 0, () => {
      const raw: MockNoticeWorkflowRaw = {
        workflow_id: 'wf_1', user_id: 'user_demo_001', source_id: 'src_manual',
        notice_id: 'notice_1', status: 'WAITING_CONFIRMATION', confidence: 0.5,
        uncertainty: ['deadline', 'location'], materials: [], steps: [], source_evidence: [],
        actions: [], created_at: '', updated_at: ''
      };
      const wf: NoticeWorkflow = AgentDtoParser.noticeWorkflow(raw as Object as Record<string, Object>);
      expect(wf.status).assertEqual(NoticeWorkflowStatus.WAITING_CONFIRMATION);
      expect(wf.uncertainty.missing_fields.length).assertEqual(2);
      expect(wf.uncertainty.confidence).assertEqual('0.5');
    });

    it('keeps approval pending when EXPIRED (no silent auto-approve)', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_nw');
      view.pendingApprovalId = 'apv_nw';
      const expired: AgentApproval = {
        approval_id: 'apv_nw', run_id: 'run_nw', status: ApprovalStatus.EXPIRED,
        risk_level: RiskLevel.MANUAL_ONLY, action_summary: '手动提交',
        expires_at: '2026-09-12T12:35:00+08:00', resolved_at: null, decision_reason: null
      };
      view = AgentEventReducer.applyApproval(view, expired);
      expect(view.pendingApprovalId).assertEqual('apv_nw');
    });

    it('uses stable Idempotency-Key for notice workflow and action decisions', 0, () => {
      const wfKey: string = IdempotencyKey.forNoticeWorkflow('notice_1');
      const decisionKey: string = IdempotencyKey.forNoticeActionDecision('act_1', 'approved');
      const executeKey: string = IdempotencyKey.forNoticeActionExecute('act_1');
      expect(wfKey).assertEqual('nw:workflow:notice_1');
      expect(decisionKey).assertEqual('nw:action:decision:act_1:approved');
      expect(executeKey).assertEqual('nw:action:execute:act_1');
    });

    it('deduplicates repeated notice delivery by stable workflow key', 0, () => {
      const key1: string = IdempotencyKey.forNoticeWorkflow('notice_1');
      const key2: string = IdempotencyKey.forNoticeWorkflow('notice_1');
      expect(key1).assertEqual(key2);
    });
  });
}
