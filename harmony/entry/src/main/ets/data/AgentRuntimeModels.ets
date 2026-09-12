// Agent Runtime v1 契约模型。
// 服务端 ID 统一使用 string；未知 enum 安全回退到 UNKNOWN，UI 不崩溃。
// 客户端不计算风险、学术政策、计划调整或自动化资格。

// ===== Runtime 基础枚举 =====

export enum RunStatus {
  QUEUED = 'QUEUED',
  RUNNING = 'RUNNING',
  AWAITING_APPROVAL = 'AWAITING_APPROVAL',
  SUCCEEDED = 'SUCCEEDED',
  PARTIAL = 'PARTIAL',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
  UNKNOWN = 'UNKNOWN'
}

export enum RunPhase {
  CONTEXT_BUILDING = 'CONTEXT_BUILDING',
  WAITING_FOR_MODEL = 'WAITING_FOR_MODEL',
  VALIDATING_OUTPUT = 'VALIDATING_OUTPUT',
  WAITING_FOR_TOOL = 'WAITING_FOR_TOOL',
  WAITING_FOR_APPROVAL = 'WAITING_FOR_APPROVAL',
  PERSISTING_RESULT = 'PERSISTING_RESULT',
  RECOVERY_CHECKING = 'RECOVERY_CHECKING',
  IDLE = 'IDLE',
  UNKNOWN = 'UNKNOWN'
}

export enum RiskLevel {
  AUTO_SAFE = 'AUTO_SAFE',
  CONFIRM_REQUIRED = 'CONFIRM_REQUIRED',
  MANUAL_ONLY = 'MANUAL_ONLY',
  UNKNOWN = 'UNKNOWN'
}

export enum AgentEventType {
  RUN_QUEUED = 'RUN_QUEUED',
  RUN_STARTED = 'RUN_STARTED',
  CONTEXT_READY = 'CONTEXT_READY',
  MODEL_STARTED = 'MODEL_STARTED',
  MODEL_COMPLETED = 'MODEL_COMPLETED',
  MODEL_FALLBACK = 'MODEL_FALLBACK',
  TOOL_STARTED = 'TOOL_STARTED',
  TOOL_COMPLETED = 'TOOL_COMPLETED',
  TOOL_FAILED = 'TOOL_FAILED',
  APPROVAL_REQUIRED = 'APPROVAL_REQUIRED',
  APPROVAL_RESOLVED = 'APPROVAL_RESOLVED',
  ARTIFACT_CREATED = 'ARTIFACT_CREATED',
  RUN_PARTIAL = 'RUN_PARTIAL',
  RUN_COMPLETED = 'RUN_COMPLETED',
  RUN_FAILED = 'RUN_FAILED',
  RUN_CANCELLED = 'RUN_CANCELLED',
  UNKNOWN = 'UNKNOWN'
}

export enum ApprovalStatus {
  PENDING = 'PENDING',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
  EXPIRED = 'EXPIRED',
  UNKNOWN = 'UNKNOWN'
}

export enum ArtifactType {
  FINAL_REVIEW_PLAN = 'FINAL_REVIEW_PLAN',
  DAILY_AGENDA = 'DAILY_AGENDA',
  NOTICE_CHECKLIST = 'NOTICE_CHECKLIST',
  COURSE_RESEARCH_REPORT = 'COURSE_RESEARCH_REPORT',
  CITATION_BUNDLE = 'CITATION_BUNDLE',
  UNKNOWN = 'UNKNOWN'
}

// ===== 错误信封 =====

export enum AgentErrorCode {
  AGENT_INVALID_STATE = 'AGENT_INVALID_STATE',
  AGENT_PERMISSION_DENIED = 'AGENT_PERMISSION_DENIED',
  AGENT_TOOL_REJECTED = 'AGENT_TOOL_REJECTED',
  AGENT_APPROVAL_REQUIRED = 'AGENT_APPROVAL_REQUIRED',
  AGENT_PROVIDER_UNAVAILABLE = 'AGENT_PROVIDER_UNAVAILABLE',
  AGENT_CONTEXT_EXPIRED = 'AGENT_CONTEXT_EXPIRED',
  AGENT_IDEMPOTENCY_CONFLICT = 'AGENT_IDEMPOTENCY_CONFLICT',
  AGENT_RUN_NOT_FOUND = 'AGENT_RUN_NOT_FOUND',
  AGENT_RUN_CANCELLED = 'AGENT_RUN_CANCELLED',
  AGENT_OUTPUT_SCHEMA_INVALID = 'AGENT_OUTPUT_SCHEMA_INVALID',
  AGENT_SOURCE_POLICY_VIOLATION = 'AGENT_SOURCE_POLICY_VIOLATION',
  AGENT_ACADEMIC_POLICY_RESTRICTED = 'AGENT_ACADEMIC_POLICY_RESTRICTED',
  UNKNOWN = 'UNKNOWN'
}

export interface AgentErrorEnvelope {
  code: AgentErrorCode;
  message: string;
  request_id: string;
  details?: Record<string, string>;
}

// ===== Runtime 核心 DTO =====

export interface AgentProgress {
  current: number;
  total: number;
  percent: number;
}

export interface AgentEvent {
  id: string;
  type: AgentEventType;
  run_id: string;
  sequence: number;
  status: RunStatus;
  phase: RunPhase;
  role: string | null;
  summary: string;
  progress: AgentProgress | null;
  artifact_id: string | null;
  approval_id: string | null;
  created_at: string;
}

export interface AgentJob {
  job_id: string;
  user_id: string;
  job_kind: string;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  latest_run_id: string | null;
}

export interface AgentRun {
  run_id: string;
  job_id: string;
  user_id: string;
  status: RunStatus;
  phase: RunPhase;
  risk_level: RiskLevel;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  error: AgentErrorEnvelope | null;
  artifact_ids: string[];
}

export interface AgentApproval {
  approval_id: string;
  run_id: string;
  status: ApprovalStatus;
  risk_level: RiskLevel;
  action_summary: string;
  expires_at: string;
  resolved_at: string | null;
  decision_reason: string | null;
}

export interface AgentArtifact {
  artifact_id: string;
  run_id: string;
  user_id: string;
  artifact_type: ArtifactType;
  version: number;
  mime_type: string;
  size_bytes: number;
  content_hash: string;
  download_url: string;
  created_at: string;
}

// ===== 期末复习领域 =====

export enum PlanVersionStatus {
  DRAFT = 'DRAFT',
  ACTIVE = 'ACTIVE',
  SUPERSEDED = 'SUPERSEDED',
  UNKNOWN = 'UNKNOWN'
}

export enum AdjustmentProposalStatus {
  PROPOSED = 'PROPOSED',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
  EXPIRED = 'EXPIRED',
  UNKNOWN = 'UNKNOWN'
}

export interface FinalReviewCampaign {
  campaign_id: string;
  user_id: string;
  exam_ids: string[];
  daily_capacity_minutes: number;
  status: RunStatus;
  active_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface FinalReviewPlanVersion {
  campaign_id: string;
  version: number;
  status: PlanVersionStatus;
  created_at: string;
  summary: string;
  daily_items: FinalReviewDailyItem[];
}

export interface FinalReviewDailyItem {
  item_id: string;
  campaign_id: string;
  version: number;
  date: string;
  course_name: string;
  topic: string;
  planned_minutes: number;
  completed: boolean;
}

export interface FinalReviewDailyAgenda {
  campaign_id: string;
  date: string;
  items: FinalReviewDailyItem[];
}

export interface FinalReviewAdjustmentProposal {
  proposal_id: string;
  campaign_id: string;
  status: AdjustmentProposalStatus;
  risk_level: RiskLevel;
  summary: string;
  rationale: string;
  created_at: string;
  resolved_at: string | null;
}

export interface FinalReviewCheckIn {
  campaign_id: string;
  date: string;
  completed_item_ids: string[];
  difficulty: string;
  feedback: string;
}

// ===== 课程研究领域 =====

export enum AcademicPolicy {
  ALLOWED = 'ALLOWED',
  LIMITED = 'LIMITED',
  EXAM_RESTRICTED = 'EXAM_RESTRICTED',
  AI_PROHIBITED = 'AI_PROHIBITED',
  UNKNOWN = 'UNKNOWN'
}

export enum AssistanceMode {
  HINT = 'HINT',
  EXPLAIN = 'EXPLAIN',
  REVIEW = 'REVIEW',
  FULL_SOLUTION = 'FULL_SOLUTION',
  UNKNOWN = 'UNKNOWN'
}

export enum CitationVerification {
  VERIFIED = 'VERIFIED',
  PARTIAL = 'PARTIAL',
  FAILED = 'FAILED',
  UNKNOWN = 'UNKNOWN'
}

export interface CourseSourcePolicy {
  course_material_priority: boolean;
  allow_web: boolean;
  allow_user_upload: boolean;
}

export interface CourseResearchRun {
  run_id: string;
  user_id: string;
  question: string;
  course_id: string;
  assistance_mode: AssistanceMode;
  academic_policy: AcademicPolicy;
  source_policy: CourseSourcePolicy;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  artifact_ids: string[];
}

export interface CourseResearchSource {
  source_id: string;
  run_id: string;
  title: string;
  url: string;
  verification: CitationVerification;
  is_course_material: boolean;
  retrieved_at: string;
}

export interface CourseResearchRoleProgress {
  role: string;
  status: RunStatus;
  summary: string;
}

// ===== 通知事务领域 =====

export enum NoticeWorkflowStatus {
  CREATED = 'CREATED',
  ANALYZING = 'ANALYZING',
  WAITING_CONFIRMATION = 'WAITING_CONFIRMATION',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  EXPIRED = 'EXPIRED',
  FAILED = 'FAILED',
  UNKNOWN = 'UNKNOWN'
}

export enum NoticeActionStatus {
  PROPOSED = 'PROPOSED',
  APPROVED = 'APPROVED',
  EXECUTING = 'EXECUTING',
  DONE = 'DONE',
  REJECTED = 'REJECTED',
  FAILED = 'FAILED',
  EXPIRED = 'EXPIRED',
  UNKNOWN = 'UNKNOWN'
}

export interface NoticeSource {
  source_id: string;
  code: string;
  display_name: string;
  permission_scope: string;
  enabled: boolean;
}

export interface NoticeUncertainty {
  missing_fields: string[];
  confidence: string;
  notes: string;
}

export interface NoticeWorkflowAction {
  action_id: string;
  workflow_id: string;
  title: string;
  risk_level: RiskLevel;
  status: NoticeActionStatus;
  materials: string[];
  is_external: boolean;
}

export interface NoticeWorkflow {
  workflow_id: string;
  user_id: string;
  source_id: string;
  status: NoticeWorkflowStatus;
  uncertainty: NoticeUncertainty;
  actions: NoticeWorkflowAction[];
  created_at: string;
  updated_at: string;
}

// ===== 安全 enum 解析器（未知值回退 UNKNOWN） =====

export class AgentEnumParser {
  static runStatus(raw: string): RunStatus {
    const values: string[] = [
      RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.AWAITING_APPROVAL,
      RunStatus.SUCCEEDED, RunStatus.PARTIAL, RunStatus.FAILED, RunStatus.CANCELLED
    ];
    return values.indexOf(raw) >= 0 ? raw as RunStatus : RunStatus.UNKNOWN;
  }

  static runPhase(raw: string): RunPhase {
    const values: string[] = [
      RunPhase.CONTEXT_BUILDING, RunPhase.WAITING_FOR_MODEL, RunPhase.VALIDATING_OUTPUT,
      RunPhase.WAITING_FOR_TOOL, RunPhase.WAITING_FOR_APPROVAL,
      RunPhase.PERSISTING_RESULT, RunPhase.RECOVERY_CHECKING, RunPhase.IDLE
    ];
    return values.indexOf(raw) >= 0 ? raw as RunPhase : RunPhase.UNKNOWN;
  }

  static riskLevel(raw: string): RiskLevel {
    const values: string[] = [RiskLevel.AUTO_SAFE, RiskLevel.CONFIRM_REQUIRED, RiskLevel.MANUAL_ONLY];
    return values.indexOf(raw) >= 0 ? raw as RiskLevel : RiskLevel.UNKNOWN;
  }

  static eventType(raw: string): AgentEventType {
    const values: string[] = [
      AgentEventType.RUN_QUEUED, AgentEventType.RUN_STARTED, AgentEventType.CONTEXT_READY,
      AgentEventType.MODEL_STARTED, AgentEventType.MODEL_COMPLETED, AgentEventType.MODEL_FALLBACK,
      AgentEventType.TOOL_STARTED, AgentEventType.TOOL_COMPLETED, AgentEventType.TOOL_FAILED,
      AgentEventType.APPROVAL_REQUIRED, AgentEventType.APPROVAL_RESOLVED,
      AgentEventType.ARTIFACT_CREATED, AgentEventType.RUN_PARTIAL,
      AgentEventType.RUN_COMPLETED, AgentEventType.RUN_FAILED, AgentEventType.RUN_CANCELLED
    ];
    return values.indexOf(raw) >= 0 ? raw as AgentEventType : AgentEventType.UNKNOWN;
  }

  static approvalStatus(raw: string): ApprovalStatus {
    const values: string[] = [ApprovalStatus.PENDING, ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED];
    return values.indexOf(raw) >= 0 ? raw as ApprovalStatus : ApprovalStatus.UNKNOWN;
  }

  static artifactType(raw: string): ArtifactType {
    const values: string[] = [
      ArtifactType.FINAL_REVIEW_PLAN, ArtifactType.DAILY_AGENDA, ArtifactType.NOTICE_CHECKLIST,
      ArtifactType.COURSE_RESEARCH_REPORT, ArtifactType.CITATION_BUNDLE
    ];
    return values.indexOf(raw) >= 0 ? raw as ArtifactType : ArtifactType.UNKNOWN;
  }

  static errorCode(raw: string): AgentErrorCode {
    const values: string[] = [
      AgentErrorCode.AGENT_INVALID_STATE, AgentErrorCode.AGENT_PERMISSION_DENIED,
      AgentErrorCode.AGENT_TOOL_REJECTED, AgentErrorCode.AGENT_APPROVAL_REQUIRED,
      AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE, AgentErrorCode.AGENT_CONTEXT_EXPIRED,
      AgentErrorCode.AGENT_IDEMPOTENCY_CONFLICT, AgentErrorCode.AGENT_RUN_NOT_FOUND,
      AgentErrorCode.AGENT_RUN_CANCELLED, AgentErrorCode.AGENT_OUTPUT_SCHEMA_INVALID,
      AgentErrorCode.AGENT_SOURCE_POLICY_VIOLATION, AgentErrorCode.AGENT_ACADEMIC_POLICY_RESTRICTED
    ];
    return values.indexOf(raw) >= 0 ? raw as AgentErrorCode : AgentErrorCode.UNKNOWN;
  }

  static academicPolicy(raw: string): AcademicPolicy {
    const values: string[] = [
      AcademicPolicy.ALLOWED, AcademicPolicy.LIMITED,
      AcademicPolicy.EXAM_RESTRICTED, AcademicPolicy.AI_PROHIBITED
    ];
    return values.indexOf(raw) >= 0 ? raw as AcademicPolicy : AcademicPolicy.UNKNOWN;
  }

  static assistanceMode(raw: string): AssistanceMode {
    const values: string[] = [
      AssistanceMode.HINT, AssistanceMode.EXPLAIN, AssistanceMode.REVIEW, AssistanceMode.FULL_SOLUTION
    ];
    return values.indexOf(raw) >= 0 ? raw as AssistanceMode : AssistanceMode.UNKNOWN;
  }

  static citationVerification(raw: string): CitationVerification {
    const values: string[] = [CitationVerification.VERIFIED, CitationVerification.PARTIAL, CitationVerification.FAILED];
    return values.indexOf(raw) >= 0 ? raw as CitationVerification : CitationVerification.UNKNOWN;
  }

  static planVersionStatus(raw: string): PlanVersionStatus {
    const values: string[] = [PlanVersionStatus.DRAFT, PlanVersionStatus.ACTIVE, PlanVersionStatus.SUPERSEDED];
    return values.indexOf(raw) >= 0 ? raw as PlanVersionStatus : PlanVersionStatus.UNKNOWN;
  }

  static adjustmentProposalStatus(raw: string): AdjustmentProposalStatus {
    const values: string[] = [
      AdjustmentProposalStatus.PROPOSED, AdjustmentProposalStatus.APPROVED,
      AdjustmentProposalStatus.REJECTED, AdjustmentProposalStatus.EXPIRED
    ];
    return values.indexOf(raw) >= 0 ? raw as AdjustmentProposalStatus : AdjustmentProposalStatus.UNKNOWN;
  }

  static noticeWorkflowStatus(raw: string): NoticeWorkflowStatus {
    const values: string[] = [
      NoticeWorkflowStatus.CREATED, NoticeWorkflowStatus.ANALYZING,
      NoticeWorkflowStatus.WAITING_CONFIRMATION, NoticeWorkflowStatus.PROCESSING,
      NoticeWorkflowStatus.COMPLETED, NoticeWorkflowStatus.EXPIRED, NoticeWorkflowStatus.FAILED
    ];
    return values.indexOf(raw) >= 0 ? raw as NoticeWorkflowStatus : NoticeWorkflowStatus.UNKNOWN;
  }

  static noticeActionStatus(raw: string): NoticeActionStatus {
    const values: string[] = [
      NoticeActionStatus.PROPOSED, NoticeActionStatus.APPROVED, NoticeActionStatus.EXECUTING,
      NoticeActionStatus.DONE, NoticeActionStatus.REJECTED, NoticeActionStatus.FAILED, NoticeActionStatus.EXPIRED
    ];
    return values.indexOf(raw) >= 0 ? raw as NoticeActionStatus : NoticeActionStatus.UNKNOWN;
  }
}

// ===== DTO 解析器（从原始 JSON 对象安全构造，未知 enum 回退） =====

export class AgentDtoParser {
  static progress(raw: Record<string, number> | null): AgentProgress | null {
    if (raw === null) return null;
    const current: number = raw.current ?? 0;
    const total: number = raw.total ?? 0;
    const percent: number = raw.percent ?? 0;
    return { current: current, total: total, percent: percent };
  }

  static event(raw: Record<string, Object>): AgentEvent {
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
      progress: AgentDtoParser.progress(progressRaw),
      artifact_id: artifactId,
      approval_id: approvalId,
      created_at: createdAt
    };
  }

  static errorEnvelope(raw: Record<string, Object>): AgentErrorEnvelope {
    const codeRaw: string = (raw.code ?? '') as string;
    const message: string = (raw.message ?? '') as string;
    const requestId: string = (raw.request_id ?? '') as string;
    const details: Record<string, string> | undefined = raw.details === null || raw.details === undefined
      ? undefined : raw.details as Record<string, string>;
    return {
      code: AgentEnumParser.errorCode(codeRaw),
      message: message,
      request_id: requestId,
      details: details
    };
  }

  static run(raw: Record<string, Object>): AgentRun {
    const artifactIdsRaw: Object = raw.artifact_ids ?? [];
    const artifactIds: string[] = Array.isArray(artifactIdsRaw) ? artifactIdsRaw as string[] : [];
    const errorRaw: Record<string, Object> | null = raw.error === null || raw.error === undefined
      ? null : raw.error as Record<string, Object>;
    return {
      run_id: (raw.run_id ?? '') as string,
      job_id: (raw.job_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      status: AgentEnumParser.runStatus((raw.status ?? '') as string),
      phase: AgentEnumParser.runPhase((raw.phase ?? '') as string),
      risk_level: AgentEnumParser.riskLevel((raw.risk_level ?? '') as string),
      started_at: raw.started_at === null || raw.started_at === undefined ? null : raw.started_at as string,
      finished_at: raw.finished_at === null || raw.finished_at === undefined ? null : raw.finished_at as string,
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string,
      error: errorRaw === null ? null : AgentDtoParser.errorEnvelope(errorRaw),
      artifact_ids: artifactIds
    };
  }

  static approval(raw: Record<string, Object>): AgentApproval {
    return {
      approval_id: (raw.approval_id ?? '') as string,
      run_id: (raw.run_id ?? '') as string,
      status: AgentEnumParser.approvalStatus((raw.status ?? '') as string),
      risk_level: AgentEnumParser.riskLevel((raw.risk_level ?? '') as string),
      action_summary: (raw.action_summary ?? '') as string,
      expires_at: (raw.expires_at ?? '') as string,
      resolved_at: raw.resolved_at === null || raw.resolved_at === undefined ? null : raw.resolved_at as string,
      decision_reason: raw.decision_reason === null || raw.decision_reason === undefined
        ? null : raw.decision_reason as string
    };
  }

  static artifact(raw: Record<string, Object>): AgentArtifact {
    return {
      artifact_id: (raw.artifact_id ?? '') as string,
      run_id: (raw.run_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      artifact_type: AgentEnumParser.artifactType((raw.artifact_type ?? '') as string),
      version: (raw.version ?? 0) as number,
      mime_type: (raw.mime_type ?? '') as string,
      size_bytes: (raw.size_bytes ?? 0) as number,
      content_hash: (raw.content_hash ?? '') as string,
      download_url: (raw.download_url ?? '') as string,
      created_at: (raw.created_at ?? '') as string
    };
  }

  static job(raw: Record<string, Object>): AgentJob {
    return {
      job_id: (raw.job_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      job_kind: (raw.job_kind ?? '') as string,
      status: AgentEnumParser.runStatus((raw.status ?? '') as string),
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string,
      latest_run_id: raw.latest_run_id === null || raw.latest_run_id === undefined
        ? null : raw.latest_run_id as string
    };
  }

  static finalReviewCampaign(raw: Record<string, Object>): FinalReviewCampaign {
    const examIdsRaw: Object = raw.exam_ids ?? [];
    const examIds: string[] = Array.isArray(examIdsRaw) ? examIdsRaw as string[] : [];
    return {
      campaign_id: (raw.campaign_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      exam_ids: examIds,
      daily_capacity_minutes: (raw.daily_capacity_minutes ?? 0) as number,
      status: AgentEnumParser.runStatus((raw.status ?? '') as string),
      active_version: raw.active_version === null || raw.active_version === undefined
        ? null : raw.active_version as number,
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string
    };
  }

  static finalReviewDailyItem(raw: Record<string, Object>): FinalReviewDailyItem {
    return {
      item_id: (raw.item_id ?? '') as string,
      campaign_id: (raw.campaign_id ?? '') as string,
      version: (raw.version ?? 0) as number,
      date: (raw.date ?? '') as string,
      course_name: (raw.course_name ?? '') as string,
      topic: (raw.topic ?? '') as string,
      planned_minutes: (raw.planned_minutes ?? 0) as number,
      completed: (raw.completed ?? false) as boolean
    };
  }

  static finalReviewPlanVersion(raw: Record<string, Object>): FinalReviewPlanVersion {
    const itemsRaw: Object = raw.daily_items ?? [];
    const itemsArr: Record<string, Object>[] = Array.isArray(itemsRaw) ? itemsRaw as Record<string, Object>[] : [];
    return {
      campaign_id: (raw.campaign_id ?? '') as string,
      version: (raw.version ?? 0) as number,
      status: AgentEnumParser.planVersionStatus((raw.status ?? '') as string),
      created_at: (raw.created_at ?? '') as string,
      summary: (raw.summary ?? '') as string,
      daily_items: itemsArr.map((item: Record<string, Object>) => AgentDtoParser.finalReviewDailyItem(item))
    };
  }

  static finalReviewAdjustmentProposal(raw: Record<string, Object>): FinalReviewAdjustmentProposal {
    return {
      proposal_id: (raw.proposal_id ?? '') as string,
      campaign_id: (raw.campaign_id ?? '') as string,
      status: AgentEnumParser.adjustmentProposalStatus((raw.status ?? '') as string),
      risk_level: AgentEnumParser.riskLevel((raw.risk_level ?? '') as string),
      summary: (raw.summary ?? '') as string,
      rationale: (raw.rationale ?? '') as string,
      created_at: (raw.created_at ?? '') as string,
      resolved_at: raw.resolved_at === null || raw.resolved_at === undefined ? null : raw.resolved_at as string
    };
  }

  static courseSourcePolicy(raw: Record<string, Object>): CourseSourcePolicy {
    return {
      course_material_priority: (raw.course_material_priority ?? false) as boolean,
      allow_web: (raw.allow_web ?? false) as boolean,
      allow_user_upload: (raw.allow_user_upload ?? false) as boolean
    };
  }

  static courseResearchRun(raw: Record<string, Object>): CourseResearchRun {
    const artifactIdsRaw: Object = raw.artifact_ids ?? [];
    const artifactIds: string[] = Array.isArray(artifactIdsRaw) ? artifactIdsRaw as string[] : [];
    return {
      run_id: (raw.run_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      question: (raw.question ?? '') as string,
      course_id: (raw.course_id ?? '') as string,
      assistance_mode: AgentEnumParser.assistanceMode((raw.assistance_mode ?? '') as string),
      academic_policy: AgentEnumParser.academicPolicy((raw.academic_policy ?? '') as string),
      source_policy: AgentDtoParser.courseSourcePolicy(
        (raw.source_policy ?? {}) as Record<string, Object>),
      status: AgentEnumParser.runStatus((raw.status ?? '') as string),
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string,
      artifact_ids: artifactIds
    };
  }

  static courseResearchSource(raw: Record<string, Object>): CourseResearchSource {
    return {
      source_id: (raw.source_id ?? '') as string,
      run_id: (raw.run_id ?? '') as string,
      title: (raw.title ?? '') as string,
      url: (raw.url ?? '') as string,
      verification: AgentEnumParser.citationVerification((raw.verification ?? '') as string),
      is_course_material: (raw.is_course_material ?? false) as boolean,
      retrieved_at: (raw.retrieved_at ?? '') as string
    };
  }

  static noticeSource(raw: Record<string, Object>): NoticeSource {
    return {
      source_id: (raw.source_id ?? '') as string,
      code: (raw.code ?? '') as string,
      display_name: (raw.display_name ?? '') as string,
      permission_scope: (raw.permission_scope ?? '') as string,
      enabled: (raw.enabled ?? false) as boolean
    };
  }

  static noticeUncertainty(raw: Record<string, Object>): NoticeUncertainty {
    const missingRaw: Object = raw.missing_fields ?? [];
    const missing: string[] = Array.isArray(missingRaw) ? missingRaw as string[] : [];
    return {
      missing_fields: missing,
      confidence: (raw.confidence ?? '') as string,
      notes: (raw.notes ?? '') as string
    };
  }

  static noticeWorkflowAction(raw: Record<string, Object>): NoticeWorkflowAction {
    const materialsRaw: Object = raw.materials ?? [];
    const materials: string[] = Array.isArray(materialsRaw) ? materialsRaw as string[] : [];
    return {
      action_id: (raw.action_id ?? '') as string,
      workflow_id: (raw.workflow_id ?? '') as string,
      title: (raw.title ?? '') as string,
      risk_level: AgentEnumParser.riskLevel((raw.risk_level ?? '') as string),
      status: AgentEnumParser.noticeActionStatus((raw.status ?? '') as string),
      materials: materials,
      is_external: (raw.is_external ?? false) as boolean
    };
  }

  static noticeWorkflow(raw: Record<string, Object>): NoticeWorkflow {
    const actionsRaw: Object = raw.actions ?? [];
    const actionsArr: Record<string, Object>[] = Array.isArray(actionsRaw) ? actionsRaw as Record<string, Object>[] : [];
    return {
      workflow_id: (raw.workflow_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      source_id: (raw.source_id ?? '') as string,
      status: AgentEnumParser.noticeWorkflowStatus((raw.status ?? '') as string),
      uncertainty: AgentDtoParser.noticeUncertainty(
        (raw.uncertainty ?? {}) as Record<string, Object>),
      actions: actionsArr.map((action: Record<string, Object>) => AgentDtoParser.noticeWorkflowAction(action)),
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string
    };
  }
}