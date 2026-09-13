import { http } from '@kit.NetworkKit';
import { ApiClient, SseEvent } from '../data/ApiClient';
import {
  AgentJob, AgentRun, AgentEvent, AgentApproval, AgentArtifact,
  AgentErrorEnvelope, AgentDtoParser,
  FinalReviewCampaign, FinalReviewPlanVersion, FinalReviewDailyAgenda,
  FinalReviewDailyItem, FinalReviewAdjustmentProposal, FinalReviewCheckIn,
  FinalReviewPlanGenerateResult, FinalReviewActivateResult, FinalReviewAdjustmentAnalyzeResult,
  FinalReviewAdjustmentDecisionResult,
  CourseResearchRun, CourseResearchSource,
  NoticeSource, NoticeWorkflow, NoticeWorkflowAction,
  RunStatus
} from '../data/AgentRuntimeModels';
import { IdempotencyKey } from '../service/AgentEventReducer';

interface CampaignCreateRequest {
  exam_ids: string[];
  daily_capacity_minutes: number;
}

interface PlanGenerateRequest {
  user_edits?: Record<string, Object>;
}

interface ActivateRequest {
  version: number;
}

interface CheckInRequest {
  report_date: string;
  completed_item_ids: string[];
  insufficient_time: boolean;
  difficulty_notes?: string;
}

interface AdjustmentDecisionRequest {
  decision: string;
  reason?: string;
}

interface ResearchRunRequest {
  course_id: string;
  question: string;
  assistance_mode: string;
  academic_policy: string;
  source_policy: Record<string, boolean>;
  user_upload_refs: string[];
}

interface ResearchArtifactsResponse {
  run_id: string;
  artifacts: Record<string, Object>[];
  sources: Record<string, Object>[];
}

interface ActionDecisionRequest {
  decision: string;
}

interface ApprovalDecisionRequest {
  decision: string;
  reason?: string;
}

// Agent Runtime 仓库：客户端只发起请求与展示，不做领域决策。
// 写操作携带稳定 Idempotency-Key，页面重建不重复提交。
export class AgentRuntimeRepository {
  private readonly client: ApiClient;

  constructor(client: ApiClient) {
    this.client = client;
  }

  // ===== Runtime 公共 =====

  async capabilities(): Promise<Record<string, Object>> {
    return this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, 'agent-runtime/capabilities');
  }

  async createJob(jobKind: string, idempotencyKey: string, payload?: object): Promise<AgentJob> {
    const body: Record<string, Object> = { job_kind: jobKind };
    if (payload !== undefined) {
      const keys: string[] = Object.keys(payload);
      for (let i: number = 0; i < keys.length; i++) {
        body[keys[i]] = (payload as Record<string, Object>)[keys[i]];
      }
    }
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, 'agent-jobs', { 'Idempotency-Key': idempotencyKey }, body);
    return AgentDtoParser.job(raw);
  }

  async getJob(jobId: string): Promise<AgentJob> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `agent-jobs/${encodeURIComponent(jobId)}`);
    return AgentDtoParser.job(raw);
  }

  async getRun(runId: string): Promise<AgentRun> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `agent-runs/${encodeURIComponent(runId)}`);
    return AgentDtoParser.run(raw);
  }

  async getApproval(approvalId: string): Promise<AgentApproval> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `agent-approvals/${encodeURIComponent(approvalId)}`);
    return AgentDtoParser.approval(raw);
  }

  async cancelRun(runId: string, idempotencyKey: string): Promise<AgentRun> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `agent-runs/${encodeURIComponent(runId)}/cancel`,
      { 'Idempotency-Key': idempotencyKey }, {});
    return AgentDtoParser.run(raw);
  }

  async listEvents(runId: string): Promise<AgentEvent[]> {
    const raw: Record<string, Object>[] = await this.client.request<Record<string, Object>[]>(
      http.RequestMethod.GET, `agent-runs/${encodeURIComponent(runId)}/events`);
    return raw.map((item: Record<string, Object>) => AgentDtoParser.event(item));
  }

  // SSE 订阅：Bearer + Last-Event-ID 由 ApiClient 注入；回调按 sequence 去重。
  async streamEvents(
    runId: string,
    lastEventId: string,
    onEvent: (event: SseEvent) => void
  ): Promise<void> {
    await this.client.streamAgentEvents(
      `agent-runs/${encodeURIComponent(runId)}/events/stream`,
      lastEventId,
      onEvent
    );
  }

  async resolveApproval(
    approvalId: string,
    decision: string,
    reason: string,
    idempotencyKey: string
  ): Promise<AgentApproval> {
    const body: ApprovalDecisionRequest = { decision: decision.toUpperCase(), reason: reason };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `agent-approvals/${encodeURIComponent(approvalId)}/decision`,
      { 'Idempotency-Key': idempotencyKey }, body);
    return AgentDtoParser.approval(raw);
  }

  async getArtifact(artifactId: string): Promise<AgentArtifact> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `agent-artifacts/${encodeURIComponent(artifactId)}`);
    return AgentDtoParser.artifact(raw);
  }

  async downloadArtifact(artifactId: string): Promise<ArrayBuffer> {
    return this.client.requestBinary(`agent-artifacts/${encodeURIComponent(artifactId)}`);
  }

  // ===== 期末复习 =====

  async listCampaigns(): Promise<FinalReviewCampaign[]> {
    const raw: Record<string, Object>[] = await this.client.request<Record<string, Object>[]>(
      http.RequestMethod.GET, 'final-review/campaigns');
    return raw.map((item: Record<string, Object>) => AgentDtoParser.finalReviewCampaign(item));
  }

  async createCampaign(
    examIds: string[],
    dailyCapacityMinutes: number
  ): Promise<FinalReviewCampaign> {
    const body: CampaignCreateRequest = { exam_ids: examIds, daily_capacity_minutes: dailyCapacityMinutes };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, 'final-review/campaigns',
      { 'Idempotency-Key': IdempotencyKey.forCampaignCreate(examIds) }, body);
    return AgentDtoParser.finalReviewCampaign(raw);
  }

  async getCampaign(campaignId: string): Promise<FinalReviewCampaign> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `final-review/campaigns/${encodeURIComponent(campaignId)}`);
    return AgentDtoParser.finalReviewCampaign(raw);
  }

  async generatePlan(campaignId: string, userEdits?: Record<string, Object>): Promise<FinalReviewPlanGenerateResult> {
    const body: PlanGenerateRequest = { user_edits: userEdits };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `final-review/campaigns/${encodeURIComponent(campaignId)}/plans/generate`,
      { 'Idempotency-Key': IdempotencyKey.forPlanGenerate(campaignId) }, body);
    return {
      run_id: (raw.run_id ?? '') as string,
      version: (raw.version ?? 0) as number,
      plan: (raw.plan ?? {}) as Record<string, Object>,
      risk_level: AgentDtoParser.finalReviewPlanVersion({ risk_level: raw.risk_level }).risk_level,
      requires_approval: (raw.requires_approval ?? false) as boolean,
      approval_id: raw.approval_id === null || raw.approval_id === undefined ? null : raw.approval_id as string
    };
  }

  async listPlanVersions(campaignId: string): Promise<FinalReviewPlanVersion[]> {
    const raw: Record<string, Object>[] = await this.client.request<Record<string, Object>[]>(
      http.RequestMethod.GET, `final-review/campaigns/${encodeURIComponent(campaignId)}/plan-versions`);
    return raw.map((item: Record<string, Object>) => AgentDtoParser.finalReviewPlanVersion(item));
  }

  async getPlanVersion(campaignId: string, version: number): Promise<FinalReviewPlanVersion> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `final-review/campaigns/${encodeURIComponent(campaignId)}/plan-versions/${version}`);
    return AgentDtoParser.finalReviewPlanVersion(raw);
  }

  async activateCampaign(campaignId: string, version: number): Promise<FinalReviewActivateResult> {
    const body: ActivateRequest = { version: version };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `final-review/campaigns/${encodeURIComponent(campaignId)}/activate`,
      { 'Idempotency-Key': IdempotencyKey.forCampaignActivate(campaignId, version) }, body);
    return {
      campaign_id: (raw.campaign_id ?? '') as string,
      active_version: (raw.active_version ?? 0) as number,
      activated: (raw.activated ?? false) as boolean
    };
  }

  async getTodayAgenda(campaignId: string): Promise<FinalReviewDailyAgenda> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `final-review/campaigns/${encodeURIComponent(campaignId)}/agendas/today`);
    const itemsRaw: Object = raw.items ?? [];
    const itemsArr: Record<string, Object>[] = Array.isArray(itemsRaw) ? itemsRaw as Record<string, Object>[] : [];
    return {
      agenda_id: (raw.agenda_id ?? '') as string,
      campaign_id: (raw.campaign_id ?? '') as string,
      plan_version: (raw.plan_version ?? 0) as number,
      agenda_date: (raw.agenda_date ?? '') as string,
      total_minutes: (raw.total_minutes ?? 0) as number,
      items: itemsArr.map((item: Record<string, Object>) => AgentDtoParser.finalReviewDailyItem(item))
    };
  }

  async completeDailyItem(itemId: string): Promise<FinalReviewDailyItem> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `final-review/daily-items/${encodeURIComponent(itemId)}/complete`,
      { 'Idempotency-Key': IdempotencyKey.forDailyItemComplete(itemId) }, {});
    return AgentDtoParser.finalReviewDailyItem(raw);
  }

  async dailyCheckIn(
    campaignId: string,
    date: string,
    completedItemIds: string[],
    difficulty: string,
    feedback: string
  ): Promise<FinalReviewCheckIn> {
    const body: CheckInRequest = {
      report_date: date,
      completed_item_ids: completedItemIds,
      insufficient_time: difficulty === '紧张',
      difficulty_notes: feedback
    };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `final-review/campaigns/${encodeURIComponent(campaignId)}/daily-checkins`,
      { 'Idempotency-Key': IdempotencyKey.forDailyCheckIn(campaignId, date) }, body);
    return {
      recorded: (raw.recorded ?? false) as boolean,
      evidence_count: (raw.evidence_count ?? 0) as number
    };
  }

  async analyzeAdjustment(campaignId: string): Promise<FinalReviewAdjustmentAnalyzeResult> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `final-review/campaigns/${encodeURIComponent(campaignId)}/adjustments/analyze`,
      { 'Idempotency-Key': IdempotencyKey.forAdjustmentAnalyze(campaignId) }, {});
    return {
      run_id: (raw.run_id ?? '') as string,
      proposal_id: (raw.proposal_id ?? '') as string,
      risk_level: AgentDtoParser.finalReviewAdjustmentProposal({ risk_level: raw.risk_level }).risk_level,
      requires_approval: (raw.requires_approval ?? false) as boolean,
      approval_id: raw.approval_id === null || raw.approval_id === undefined ? null : raw.approval_id as string
    };
  }

  async listAdjustmentProposals(campaignId: string): Promise<FinalReviewAdjustmentProposal[]> {
    const raw: Record<string, Object>[] = await this.client.request<Record<string, Object>[]>(
      http.RequestMethod.GET, `final-review/campaigns/${encodeURIComponent(campaignId)}/adjustment-proposals`);
    return raw.map((item: Record<string, Object>) => AgentDtoParser.finalReviewAdjustmentProposal(item));
  }

  async resolveAdjustment(
    proposalId: string,
    decision: string,
    reason: string
  ): Promise<FinalReviewAdjustmentDecisionResult> {
    const body: AdjustmentDecisionRequest = { decision: decision.toUpperCase(), reason: reason };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `final-review/adjustment-proposals/${encodeURIComponent(proposalId)}/decision`,
      { 'Idempotency-Key': IdempotencyKey.forAdjustmentDecision(proposalId, decision) }, body);
    return {
      proposal_id: (raw.proposal_id ?? '') as string,
      status: AgentDtoParser.finalReviewAdjustmentProposal({ status: raw.status }).status,
      new_version: raw.new_version === null || raw.new_version === undefined ? null : raw.new_version as number,
      active_version: raw.active_version === null || raw.active_version === undefined ? null : raw.active_version as number
    };
  }

  // ===== 课程研究 =====

  async listResearchRuns(): Promise<CourseResearchRun[]> {
    const raw: Record<string, Object>[] = await this.client.request<Record<string, Object>[]>(
      http.RequestMethod.GET, 'course-research/runs');
    return raw.map((item: Record<string, Object>) => AgentDtoParser.courseResearchRun(item));
  }

  async createResearchRun(
    courseId: string,
    question: string,
    assistanceMode: string,
    questionHash: string
  ): Promise<CourseResearchRun> {
    const body: ResearchRunRequest = {
      course_id: courseId,
      question: question,
      assistance_mode: assistanceMode,
      academic_policy: 'UNKNOWN',
      source_policy: {
        course_material_priority: true,
        allow_web: true,
        allow_user_upload: true
      },
      user_upload_refs: []
    };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, 'course-research/runs',
      { 'Idempotency-Key': IdempotencyKey.forResearchRun(courseId, questionHash) }, body);
    return AgentDtoParser.courseResearchRun(raw);
  }

  async getResearchRun(runId: string): Promise<CourseResearchRun> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `course-research/runs/${encodeURIComponent(runId)}`);
    return AgentDtoParser.courseResearchRun(raw);
  }

  async cancelResearchRun(runId: string): Promise<CourseResearchRun> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `course-research/runs/${encodeURIComponent(runId)}/cancel`,
      { 'Idempotency-Key': `cr:cancel:${runId}` }, {});
    return AgentDtoParser.courseResearchRun(raw);
  }

  async listResearchArtifacts(runId: string): Promise<AgentArtifact[]> {
    const raw: ResearchArtifactsResponse = await this.client.request<ResearchArtifactsResponse>(
      http.RequestMethod.GET, `course-research/runs/${encodeURIComponent(runId)}/artifacts`);
    return raw.artifacts.map((item: Record<string, Object>) => AgentDtoParser.artifact(item));
  }

  async listResearchSources(runId: string): Promise<CourseResearchSource[]> {
    const raw: ResearchArtifactsResponse = await this.client.request<ResearchArtifactsResponse>(
      http.RequestMethod.GET, `course-research/runs/${encodeURIComponent(runId)}/artifacts`);
    return raw.sources.map((item: Record<string, Object>) => AgentDtoParser.courseResearchSource(item));
  }

  // ===== 通知事务 =====

  async listNoticeSources(): Promise<NoticeSource[]> {
    const raw: Record<string, Object>[] = await this.client.request<Record<string, Object>[]>(
      http.RequestMethod.GET, 'notification-sources');
    return raw.map((item: Record<string, Object>) => AgentDtoParser.noticeSource(item));
  }

  async updateNoticeSource(sourceId: string, enabled: boolean): Promise<NoticeSource> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      'PATCH' as http.RequestMethod, `notification-sources/${encodeURIComponent(sourceId)}`,
      { 'Idempotency-Key': `nw:source:${sourceId}:${enabled}` }, { automation_enabled: enabled });
    return AgentDtoParser.noticeSource(raw);
  }

  async createManualNotice(content: string): Promise<string> {
    const firstLine: string = content.split('\n')[0].trim();
    const title: string = firstLine.length > 0 ? firstLine.substring(0, 256) : '手动通知';
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, 'notices/manual',
      { 'Idempotency-Key': `nw:manual:${this.contentHash(content)}` },
      { title: title, content: content, source_name: 'manual_input' });
    return (raw.notice_id ?? raw.id ?? '') as string;
  }

  async createNoticeWorkflow(noticeId: string, _content: string, _sourceCode: string): Promise<NoticeWorkflow> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `notices/${encodeURIComponent(noticeId)}/workflow`,
      { 'Idempotency-Key': IdempotencyKey.forNoticeWorkflow(noticeId) }, {});
    return AgentDtoParser.noticeWorkflow(raw);
  }

  async getNoticeWorkflow(workflowId: string): Promise<NoticeWorkflow> {
    const raw: Record<string, Object> = await this.client.request<Record<string, Object>>(
      http.RequestMethod.GET, `notice-workflows/${encodeURIComponent(workflowId)}`);
    return AgentDtoParser.noticeWorkflow(raw);
  }

  async reanalyzeNoticeWorkflow(workflowId: string): Promise<NoticeWorkflow> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `notice-workflows/${encodeURIComponent(workflowId)}/reanalyze`,
      { 'Idempotency-Key': `nw:reanalyze:${workflowId}` }, {});
    return AgentDtoParser.noticeWorkflow(raw);
  }

  async resolveNoticeAction(actionId: string, decision: string): Promise<NoticeWorkflowAction> {
    const body: ActionDecisionRequest = { decision: decision.toUpperCase() };
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `notice-workflow-actions/${encodeURIComponent(actionId)}/decision`,
      { 'Idempotency-Key': IdempotencyKey.forNoticeActionDecision(actionId, decision) }, body);
    return AgentDtoParser.noticeWorkflowAction(raw);
  }

  async executeNoticeAction(actionId: string): Promise<NoticeWorkflowAction> {
    const raw: Record<string, Object> = await this.client.requestWithHeaders<Record<string, Object>>(
      http.RequestMethod.POST, `notice-workflow-actions/${encodeURIComponent(actionId)}/execute`,
      { 'Idempotency-Key': IdempotencyKey.forNoticeActionExecute(actionId) }, {});
    return AgentDtoParser.noticeWorkflowAction(raw);
  }

  private contentHash(content: string): string {
    let hash: number = 0;
    for (let i: number = 0; i < content.length; i++) {
      hash = (hash * 31 + content.charCodeAt(i)) & 0x7fffffff;
    }
    return hash.toString(36);
  }
}
