import { describe, expect, it } from '@ohos/hypium';
import {
  AgentEventReducer, IdempotencyKey, AgentRunView
} from '../../../main/ets/service/AgentEventReducer';
import {
  AgentEvent, AgentEventType, RunStatus, RunPhase, AgentApproval, ApprovalStatus, RiskLevel
} from '../../../main/ets/data/AgentRuntimeModels';

interface MockResumeEvent {
  id: string;
  sequence: number;
}

interface MockRawEvent {
  id: string;
  type: string;
  run_id: string;
  sequence: number;
  status: string;
  phase: string;
  role: string | null;
  summary: string;
  progress: Object | null;
  artifact_id: string | null;
  approval_id: string | null;
  created_at: string;
}

function makeEvent(id: string, sequence: number, type: AgentEventType,
  status: RunStatus, summary: string): AgentEvent {
  return {
    id: id, type: type, run_id: 'run_x', sequence: sequence,
    status: status, phase: RunPhase.IDLE, role: null, summary: summary,
    progress: null, artifact_id: null, approval_id: null,
    created_at: '2026-09-12T10:00:00+08:00'
  };
}

function makeApproval(id: string, status: ApprovalStatus, risk: RiskLevel): AgentApproval {
  return {
    approval_id: id, run_id: 'run_x', status: status, risk_level: risk,
    action_summary: '动作', expires_at: '2026-09-12T10:30:00+08:00',
    resolved_at: null, decision_reason: null
  };
}

export default function agentEventReducerTest(): void {
  describe('AgentEventReducer', () => {
    it('deduplicates events by sequence', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view = AgentEventReducer.append(view, makeEvent('e1', 1, AgentEventType.RUN_STARTED, RunStatus.RUNNING, '开始'));
      view = AgentEventReducer.append(view, makeEvent('e1_dup', 1, AgentEventType.RUN_STARTED, RunStatus.RUNNING, '重复'));
      expect(view.events.length).assertEqual(1);
      expect(view.lastSequence).assertEqual(1);
    });

    it('ignores events with sequence not greater than last seen', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view = AgentEventReducer.append(view, makeEvent('e10', 10, AgentEventType.TOOL_COMPLETED, RunStatus.RUNNING, '工具'));
      view = AgentEventReducer.append(view, makeEvent('e5', 5, AgentEventType.RUN_STARTED, RunStatus.RUNNING, '旧事件'));
      expect(view.events.length).assertEqual(1);
      expect(view.lastSequence).assertEqual(10);
    });

    it('sorts events by sequence in ascending order', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view = AgentEventReducer.append(view, makeEvent('e30', 30, AgentEventType.RUN_COMPLETED, RunStatus.SUCCEEDED, '完成'));
      view = AgentEventReducer.append(view, makeEvent('e10', 10, AgentEventType.RUN_STARTED, RunStatus.RUNNING, '开始'));
      view = AgentEventReducer.append(view, makeEvent('e20', 20, AgentEventType.TOOL_COMPLETED, RunStatus.RUNNING, '工具'));
      expect(view.events[0].sequence).assertEqual(10);
      expect(view.events[1].sequence).assertEqual(20);
      expect(view.events[2].sequence).assertEqual(30);
    });

    it('tracks last event id for SSE resume', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view = AgentEventReducer.append(view, makeEvent('evt_100', 1, AgentEventType.RUN_STARTED, RunStatus.RUNNING, '开始'));
      view = AgentEventReducer.append(view, makeEvent('evt_200', 2, AgentEventType.RUN_COMPLETED, RunStatus.SUCCEEDED, '完成'));
      expect(view.lastEventId).assertEqual('evt_200');
    });

    it('resumes from Last-Event-ID by dropping already delivered events', 0, () => {
      const e1: MockResumeEvent = { id: 'evt_1', sequence: 1 };
      const e2: MockResumeEvent = { id: 'evt_2', sequence: 2 };
      const e3: MockResumeEvent = { id: 'evt_3', sequence: 3 };
      const events: Record<string, Object>[] = [
        e1 as Object as Record<string, Object>, e2 as Object as Record<string, Object>, e3 as Object as Record<string, Object>
      ];
      const remaining: Record<string, Object>[] = AgentEventReducer.resumeFromLastEventId(events, 'evt_1');
      expect(remaining.length).assertEqual(2);
      expect((remaining[0].id as string)).assertEqual('evt_2');
    });

    it('returns all events when Last-Event-ID is empty or not found', 0, () => {
      const e1: MockResumeEvent = { id: 'evt_1', sequence: 1 };
      const e2: MockResumeEvent = { id: 'evt_2', sequence: 2 };
      const events: Record<string, Object>[] = [
        e1 as Object as Record<string, Object>, e2 as Object as Record<string, Object>
      ];
      expect(AgentEventReducer.resumeFromLastEventId(events, '').length).assertEqual(2);
      expect(AgentEventReducer.resumeFromLastEventId(events, 'evt_missing').length).assertEqual(2);
    });

    it('sets partial flag on RUN_PARTIAL and clears on RUN_COMPLETED', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view = AgentEventReducer.append(view, makeEvent('e20', 20, AgentEventType.RUN_PARTIAL, RunStatus.PARTIAL, '部分完成'));
      expect(view.partial).assertEqual(true);
      view = AgentEventReducer.append(view, makeEvent('e40', 40, AgentEventType.RUN_COMPLETED, RunStatus.SUCCEEDED, '完成'));
      expect(view.partial).assertEqual(false);
    });

    it('sets failed flag on RUN_FAILED and clears on RUN_COMPLETED', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view = AgentEventReducer.append(view, makeEvent('e50', 50, AgentEventType.RUN_FAILED, RunStatus.FAILED, '失败'));
      expect(view.failed).assertEqual(true);
      view = AgentEventReducer.append(view, makeEvent('e60', 60, AgentEventType.RUN_COMPLETED, RunStatus.SUCCEEDED, '完成'));
      expect(view.failed).assertEqual(false);
    });

    it('tracks pending approval from APPROVAL_REQUIRED and clears on APPROVAL_RESOLVED', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      const reqEvent: AgentEvent = {
        id: 'e30', type: AgentEventType.APPROVAL_REQUIRED, run_id: 'run_x', sequence: 30,
        status: RunStatus.AWAITING_APPROVAL, phase: RunPhase.WAITING_FOR_APPROVAL, role: 'planner',
        summary: '需要确认', progress: null, artifact_id: null,
        approval_id: 'apv_1', created_at: '2026-09-12T10:08:00+08:00'
      };
      view = AgentEventReducer.append(view, reqEvent);
      expect(view.pendingApprovalId).assertEqual('apv_1');
      const resolvedEvent: AgentEvent = {
        id: 'e35', type: AgentEventType.APPROVAL_RESOLVED, run_id: 'run_x', sequence: 35,
        status: RunStatus.RUNNING, phase: RunPhase.PERSISTING_RESULT, role: 'planner',
        summary: '已确认', progress: null, artifact_id: null,
        approval_id: 'apv_1', created_at: '2026-09-12T10:09:00+08:00'
      };
      view = AgentEventReducer.append(view, resolvedEvent);
      expect(view.pendingApprovalId).assertEqual(null);
    });

    it('keeps approval pending when EXPIRED or UNKNOWN (conservative)', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view.pendingApprovalId = 'apv_1';
      view = AgentEventReducer.applyApproval(view, makeApproval('apv_1', ApprovalStatus.EXPIRED, RiskLevel.CONFIRM_REQUIRED));
      expect(view.pendingApprovalId).assertEqual('apv_1');
      view = AgentEventReducer.applyApproval(view, makeApproval('apv_1', ApprovalStatus.UNKNOWN, RiskLevel.UNKNOWN));
      expect(view.pendingApprovalId).assertEqual('apv_1');
    });

    it('clears pending approval when APPROVED or REJECTED', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      view.pendingApprovalId = 'apv_1';
      view = AgentEventReducer.applyApproval(view, makeApproval('apv_1', ApprovalStatus.APPROVED, RiskLevel.CONFIRM_REQUIRED));
      expect(view.pendingApprovalId).assertEqual(null);
      view.pendingApprovalId = 'apv_1';
      view = AgentEventReducer.applyApproval(view, makeApproval('apv_1', ApprovalStatus.REJECTED, RiskLevel.CONFIRM_REQUIRED));
      expect(view.pendingApprovalId).assertEqual(null);
    });

    it('detects MANUAL_ONLY risk for gating client auto-execution', 0, () => {
      expect(AgentEventReducer.isManualOnly(RiskLevel.MANUAL_ONLY)).assertEqual(true);
      expect(AgentEventReducer.isManualOnly(RiskLevel.CONFIRM_REQUIRED)).assertEqual(false);
      expect(AgentEventReducer.isManualOnly(RiskLevel.AUTO_SAFE)).assertEqual(false);
      expect(AgentEventReducer.isManualOnly(RiskLevel.UNKNOWN)).assertEqual(false);
    });

    it('parses raw event with unknown enum without crashing', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      const raw: MockRawEvent = {
        id: 'e_weird', type: 'ALIEN_SIGNAL', run_id: 'run_x', sequence: 1,
        status: 'FROZEN', phase: 'COOKING', role: null, summary: '未知事件',
        progress: null, artifact_id: null, approval_id: null, created_at: '2026-09-12T10:00:00+08:00'
      };
      view = AgentEventReducer.appendRaw(view, raw as Object as Record<string, Object>);
      expect(view.events.length).assertEqual(1);
      expect(view.events[0].type).assertEqual(AgentEventType.UNKNOWN);
      expect(view.events[0].status).assertEqual(RunStatus.UNKNOWN);
      expect(view.events[0].phase).assertEqual(RunPhase.UNKNOWN);
    });

    it('produces stable Idempotency-Key without timestamps', 0, () => {
      const key1: string = IdempotencyKey.forCampaignCreate(['exam_b', 'exam_a']);
      const key2: string = IdempotencyKey.forCampaignCreate(['exam_a', 'exam_b']);
      expect(key1).assertEqual(key2);
      expect(key1.indexOf('fr:campaign:create:exam_a,exam_b') >= 0).assertEqual(true);

      const planKey1: string = IdempotencyKey.forPlanGenerate('camp_1');
      const planKey2: string = IdempotencyKey.forPlanGenerate('camp_1');
      expect(planKey1).assertEqual(planKey2);

      const decisionKey: string = IdempotencyKey.forApprovalDecision('apv_1', 'approved');
      expect(decisionKey).assertEqual('approval:decision:apv_1:approved');
    });

    it('produces distinct Idempotency-Key for different actions', 0, () => {
      const a: string = IdempotencyKey.forAdjustmentDecision('prop_1', 'approved');
      const b: string = IdempotencyKey.forAdjustmentDecision('prop_1', 'rejected');
      expect(a === b).assertFalse();
    });

    it('ignores events from a different run id', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_x');
      const other: AgentEvent = {
        id: 'e_other', type: AgentEventType.RUN_STARTED, run_id: 'run_y', sequence: 1,
        status: RunStatus.RUNNING, phase: RunPhase.IDLE, role: null, summary: '其他 run',
        progress: null, artifact_id: null, approval_id: null, created_at: ''
      };
      view = AgentEventReducer.append(view, other);
      expect(view.events.length).assertEqual(0);
    });
  });
}
