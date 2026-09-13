import {
  AgentEvent,
  AgentEventType,
  AgentApproval,
  ApprovalStatus,
  RunStatus,
  RunPhase,
  AgentProgress,
  RiskLevel,
  AgentEnumParser
} from '../data/AgentRuntimeModels';

// 归约后的运行视图：UI 据此渲染，不持有领域决策。
export interface AgentRunView {
  runId: string;
  status: RunStatus;
  phase: RunPhase;
  lastSummary: string;
  progress: AgentProgress | null;
  pendingApprovalId: string | null;
  artifactId: string | null;
  lastEventId: string;
  lastSequence: number;
  events: AgentEvent[];
  partial: boolean;
  failed: boolean;
}

export class AgentEventReducer {
  static initial(runId: string): AgentRunView {
    return {
      runId: runId,
      status: RunStatus.QUEUED,
      phase: RunPhase.IDLE,
      lastSummary: '',
      progress: null,
      pendingApprovalId: null,
      artifactId: null,
      lastEventId: '',
      lastSequence: 0,
      events: [],
      partial: false,
      failed: false
    };
  }

  // 按 sequence 去重追加。已见 sequence 或更小 sequence 被丢弃，保证幂等。
  static append(view: AgentRunView, event: AgentEvent): AgentRunView {
    if (event.run_id !== view.runId) return view;
    if (event.sequence <= view.lastSequence && view.lastSequence > 0) return view;
    const alreadySeen: boolean = view.events.some((e: AgentEvent) => e.sequence === event.sequence);
    if (alreadySeen) return view;
    const events: AgentEvent[] = [...view.events, event].sort(
      (a: AgentEvent, b: AgentEvent) => a.sequence - b.sequence);
    const advanced: AgentRunView = {
      runId: view.runId,
      status: view.status,
      phase: view.phase,
      lastSummary: view.lastSummary,
      progress: view.progress,
      pendingApprovalId: view.pendingApprovalId,
      artifactId: view.artifactId,
      lastEventId: event.id,
      lastSequence: event.sequence,
      events: events,
      partial: view.partial,
      failed: view.failed
    };
    return AgentEventReducer.applyEvent(advanced, event);
  }

  // 批量从原始 JSON 安全归约，未知 enum 回退 UNKNOWN 不崩溃。
  static appendRaw(view: AgentRunView, raw: Record<string, Object>): AgentRunView {
    return AgentEventReducer.append(view, AgentEventReducer.parseEvent(raw));
  }

  static parseEvent(raw: Record<string, Object>): AgentEvent {
    const id: string = (raw.id ?? '') as string;
    const typeRaw: string = (raw.type ?? '') as string;
    const runId: string = (raw.run_id ?? '') as string;
    const sequence: number = (raw.sequence ?? 0) as number;
    const statusRaw: string = (raw.status ?? '') as string;
    const phaseRaw: string = (raw.phase ?? '') as string;
    const role: string | null = raw.role === null || raw.role === undefined ? null : raw.role as string;
    const summary: string = (raw.summary ?? '') as string;
    const progressRaw: Record<string, number> | null = raw.progress === null || raw.progress === undefined
      ? null : raw.progress as Record<string, number>;
    const artifactId: string | null = raw.artifact_id === null || raw.artifact_id === undefined
      ? null : raw.artifact_id as string;
    const approvalId: string | null = raw.approval_id === null || raw.approval_id === undefined
      ? null : raw.approval_id as string;
    const createdAt: string = (raw.created_at ?? '') as string;
    return {
      id: id,
      type: AgentEnumParser.eventType(typeRaw),
      run_id: runId,
      sequence: sequence,
      status: AgentEnumParser.runStatus(statusRaw),
      phase: AgentEnumParser.runPhase(phaseRaw),
      role: role,
      summary: summary,
      progress: AgentEventReducer.parseProgress(progressRaw),
      artifact_id: artifactId,
      approval_id: approvalId,
      created_at: createdAt
    };
  }

  static parseProgress(raw: Record<string, number> | null): AgentProgress | null {
    if (raw === null) return null;
    return { current: raw.current ?? 0, total: raw.total ?? 0, percent: raw.percent ?? 0 };
  }

  // SSE 断线恢复时用 Last-Event-ID 过滤已投递事件。
  static resumeFromLastEventId(events: Record<string, Object>[], lastEventId: string): Record<string, Object>[] {
    if (lastEventId.length === 0) return events;
    const index: number = events.findIndex((e: Record<string, Object>) => (e.id ?? '') as string === lastEventId);
    if (index < 0) return events;
    return events.slice(index + 1);
  }

  // 审批保守处理：仅当 approval 存在且 status 为 PENDING/APPROVED/REJECTED 时才更新视图；
  // EXPIRED 或 UNKNOWN 不自动放行，UI 保持等待并允许刷新或返回。
  static applyApproval(view: AgentRunView, approval: AgentApproval): AgentRunView {
    if (approval.run_id !== view.runId) return view;
    if (approval.status === ApprovalStatus.EXPIRED || approval.status === ApprovalStatus.UNKNOWN) {
      return AgentEventReducer.withApproval(view, approval.approval_id);
    }
    if (approval.status === ApprovalStatus.APPROVED || approval.status === ApprovalStatus.REJECTED) {
      return AgentEventReducer.withApproval(view, null);
    }
    return AgentEventReducer.withApproval(view, approval.approval_id);
  }

  // 高风险（MANUAL_ONLY）动作不允许客户端自动标记完成。
  static isManualOnly(risk: RiskLevel): boolean {
    return risk === RiskLevel.MANUAL_ONLY;
  }

  private static applyEvent(view: AgentRunView, event: AgentEvent): AgentRunView {
    let status: RunStatus = view.status;
    let phase: RunPhase = view.phase;
    let pendingApprovalId: string | null = view.pendingApprovalId;
    let artifactId: string | null = view.artifactId;
    let partial: boolean = view.partial;
    let failed: boolean = view.failed;

    if (event.status !== RunStatus.UNKNOWN) status = event.status;
    if (event.phase !== RunPhase.UNKNOWN) phase = event.phase;
    if (event.approval_id !== null) pendingApprovalId = event.approval_id;
    if (event.artifact_id !== null) artifactId = event.artifact_id;

    if (event.type === AgentEventType.APPROVAL_RESOLVED) pendingApprovalId = null;
    if (event.type === AgentEventType.RUN_PARTIAL) partial = true;
    if (event.type === AgentEventType.RUN_COMPLETED) partial = false;
    if (event.type === AgentEventType.RUN_FAILED) failed = true;
    if (event.type === AgentEventType.RUN_COMPLETED || event.type === AgentEventType.RUN_CANCELLED) {
      failed = false;
    }

    return {
      runId: view.runId,
      status: status,
      phase: phase,
      lastSummary: event.summary.length > 0 ? event.summary : view.lastSummary,
      progress: event.progress ?? view.progress,
      pendingApprovalId: pendingApprovalId,
      artifactId: artifactId,
      lastEventId: view.lastEventId,
      lastSequence: view.lastSequence,
      events: view.events,
      partial: partial,
      failed: failed
    };
  }

  private static withApproval(view: AgentRunView, pendingApprovalId: string | null): AgentRunView {
    return {
      runId: view.runId,
      status: view.status,
      phase: view.phase,
      lastSummary: view.lastSummary,
      progress: view.progress,
      pendingApprovalId: pendingApprovalId,
      artifactId: view.artifactId,
      lastEventId: view.lastEventId,
      lastSequence: view.lastSequence,
      events: view.events,
      partial: view.partial,
      failed: view.failed
    };
  }
}

// 稳定 Idempotency-Key：同一逻辑写操作在页面重建后不重复提交。
// 由领域 + 目标 ID + 动作组成，不含时间戳或随机数。
export class IdempotencyKey {
  static forCampaignCreate(examIds: string[]): string {
    return `fr:campaign:create:${examIds.slice().sort().join(',')}`;
  }

  static forPlanGenerate(campaignId: string): string {
    return `fr:plan:generate:${campaignId}`;
  }

  static forCampaignActivate(campaignId: string, version: number): string {
    return `fr:campaign:activate:${campaignId}:${version}`;
  }

  static forDailyItemComplete(itemId: string): string {
    return `fr:item:complete:${itemId}`;
  }

  static forDailyCheckIn(campaignId: string, date: string): string {
    return `fr:checkin:${campaignId}:${date}`;
  }

  static forAdjustmentAnalyze(campaignId: string): string {
    return `fr:adjustment:analyze:${campaignId}`;
  }

  static forAdjustmentDecision(proposalId: string, decision: string): string {
    return `fr:adjustment:decision:${proposalId}:${decision}`;
  }

  static forResearchRun(courseId: string, questionHash: string): string {
    return `cr:run:${courseId}:${questionHash}`;
  }

  static forNoticeWorkflow(noticeId: string): string {
    return `nw:workflow:${noticeId}`;
  }

  static forNoticeActionDecision(actionId: string, decision: string): string {
    return `nw:action:decision:${actionId}:${decision}`;
  }

  static forNoticeActionExecute(actionId: string): string {
    return `nw:action:execute:${actionId}`;
  }

  static forApprovalDecision(approvalId: string, decision: string): string {
    return `approval:decision:${approvalId}:${decision}`;
  }
}