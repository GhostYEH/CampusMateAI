// Agent Runtime v1 契约模型。
// 服务端 ID 统一使用 string；未知 enum 安全回退到 UNKNOWN，UI 不崩溃。
// 客户端不计算风险、学术政策、计划调整或自动化资格。

// ===== Runtime 基础枚举 =====

export enum RunStatus {
  QUEUED = 'QUEUED',
  RUNNING = 'RUNNING',
  AWAITING_APPROVAL = 'AWAITING_APPROVAL',
  PAUSED = 'PAUSED',
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
  RUN_PAUSED = 'RUN_PAUSED',
  RUN_RESUMED = 'RUN_RESUMED',
  RUN_RETRIED = 'RUN_RETRIED',
  RUN_RETRY_SCHEDULED = 'RUN_RETRY_SCHEDULED',
  RUN_RECOVERY_STARTED = 'RUN_RECOVERY_STARTED',
  RUN_RECOVERED = 'RUN_RECOVERED',
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
  AGENT_CAPABILITY_DISABLED = 'AGENT_CAPABILITY_DISABLED',
  AGENT_RUNTIME_UNAVAILABLE = 'AGENT_RUNTIME_UNAVAILABLE',
  AGENT_CURSOR_INVALID = 'AGENT_CURSOR_INVALID',
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
  input_ref: Record<string, Object>;
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
  retry_of: string | null;
}

// ===== AI 学习目标执行中心 =====

export interface StudentGoal {
  goal_id: string;
  user_id: string;
  name: string;
  category: string;
  status: string;
  target_date: string | null;
  progress_percent: number;
  milestone_count: number;
  created_at: string;
  updated_at: string;
}

export interface LearningPlanSummary {
  plan_id: string;
  goal_id: string | null;
  status: string;
  stage: string;
  headline: string;
  completion_percent: number;
  planned_item_count: number;
  executed_item_count: number;
  planned_minutes: number;
  next_action: string;
  recommendations: string[];
  warning_codes: string[];
  generated_at: string;
  // 候选模型只读注解：可识别、可降级、可追溯；缺失即为"本次没有候选结果"。
  candidate_annotation: CandidateAnnotation | null;
}

// ===== 学生世界模型（只读）=====
//
// 只建模页面真正展示的字段。`value` / `state_comparison` 这类自由结构刻意不建模，
// 避免为一个展示摘要引入多态解析；降级标记（data_quality / warning_codes /
// limitations）必须建模，否则页面无法区分"真的没有"和"取不到"。

export interface CandidateAnnotation {
  available: boolean;
  capability_name: string;
  capability_version: string;
  reason: string | null;
  inference_source: string;
  model_key: string | null;
  model_version: string | null;
  prompt_version: string | null;
  input_digest: string | null;
  shadow_run_id: string | null;
  used_fallback: boolean;
  claim_codes: string[];
  summary: string | null;
  read_only: boolean;
  affects_production: boolean;
}

export interface LearnerStateSnapshot {
  snapshot_id: string;
  state_type: string;
  confidence: number;
  data_quality: string;
  projection_kind: string;
  warning_codes: string[];
  evidence_count: number;
}

export interface LearnerStateSnapshotPage {
  items: LearnerStateSnapshot[];
  total: number;
}

export interface ForecastSummary {
  forecast_id: string;
  forecast_type: string;
  probability: number | null;
  confidence: number;
  data_quality: string;
  horizon_end: string | null;
  limitations: string[];
}

export interface DataSourceControl {
  source_key: string;
  status: string;
  can_pause: boolean;
  can_resume: boolean;
}

export interface ModelCapabilityTransparency {
  capability_name: string;
  campusmate_lm_status: string;
  quality_gate_passed: boolean;
  performance_measured: boolean;
  uses_real_model_inference: boolean;
}

export interface ModelTransparency {
  capabilities: ModelCapabilityTransparency[];
  campusmate_lm_enabled: boolean;
  campusmate_lm_affects_production: boolean;
  shadow_results_modify_plans: boolean;
  read_only_canary_active: boolean;
  real_inference_observed: boolean;
  fixture_only: boolean;
}

export interface AdaptiveInterventionOutcome {
  intervention_id: string;
  plan_id: string | null;
  observation_status: string;
  execution_signal: string;
  adoption: string;
  verdict: string;
  observed_outcome: string;
  causal_claim: string;
  decision: string | null;
  decision_reason_codes: string[];
  suggested_adjustments: string[];
  decision_status: string | null;
  observation_due_at: string | null;
  warning_codes: string[];
}

export interface AdaptiveIntervention {
  intervention_id: string;
  goal_id: string;
  plan_id: string | null;
  status: string;
  strategy_code: string;
  data_quality: string | null;
  observation_due_at: string | null;
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
  preferred_periods: string[];
  rest_days: string[];
  intensity: string;
  status: string;
  active_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface FinalReviewPlanVersion {
  campaign_id: string;
  version: number;
  plan: Record<string, Object>;
  model_provider: string;
  route_policy: string;
  risk_level: RiskLevel;
  approval_id: string | null;
  supersedes_version: number | null;
  created_at: string;
}

export interface FinalReviewPlanGenerateResult {
  run_id: string;
  version: number;
  plan: Record<string, Object>;
  risk_level: RiskLevel;
  requires_approval: boolean;
  approval_id: string | null;
}

export interface FinalReviewActivateResult {
  campaign_id: string;
  active_version: number;
  activated: boolean;
}

export interface FinalReviewDailyItem {
  item_id: string;
  title: string;
  course_name: string | null;
  scheduled_minutes: number;
  sort_order: number;
  status: string;
  personal_task_id: string | null;
  difficulty: string | null;
  completed: boolean;
}

export interface FinalReviewDailyAgenda {
  agenda_id: string;
  campaign_id: string;
  plan_version: number;
  agenda_date: string;
  total_minutes: number;
  items: FinalReviewDailyItem[];
}

export interface FinalReviewAdjustmentProposal {
  proposal_id: string;
  campaign_id: string;
  status: AdjustmentProposalStatus;
  source_version: number;
  proposal: Record<string, Object>;
  risk_level: RiskLevel;
  approval_id: string | null;
  target_version: number | null;
  reason: string | null;
  summary: string;
  rationale: string;
  created_at: string;
}

export interface FinalReviewCheckIn {
  recorded: boolean;
  evidence_count: number;
}

export interface FinalReviewAdjustmentAnalyzeResult {
  run_id: string;
  proposal_id: string;
  risk_level: RiskLevel;
  requires_approval: boolean;
  approval_id: string | null;
}

export interface FinalReviewAdjustmentDecisionResult {
  proposal_id: string;
  status: AdjustmentProposalStatus;
  new_version: number | null;
  active_version: number | null;
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
  session_id: string;
  user_id: string;
  question: string;
  course_id: string | null;
  assistance_mode: AssistanceMode;
  academic_policy: AcademicPolicy;
  effective_assistance_mode: AssistanceMode;
  source_policy: CourseSourcePolicy;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  error_code: string | null;
  artifact_ids: string[];
  fallback_used: boolean;
}

export interface CourseResearchSource {
  source_id: string;
  source_type: string;
  title: string;
  url: string | null;
  snippet: string | null;
  source_ref: string | null;
  accessed_at: string;
  is_verified: boolean;
  verification_note: string | null;
  supports_claim: boolean | null;
  is_fabricated: boolean;
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
  permission_scope: string | null;
  kind: string;
  automation_enabled: boolean;
}

export interface NoticeUncertainty {
  missing_fields: string[];
  confidence: string;
  notes: string;
}

export interface NoticeWorkflowAction {
  action_id: string;
  workflow_id: string;
  action_type: string;
  title: string;
  risk_level: RiskLevel;
  status: NoticeActionStatus;
  materials: string[];
  is_external: boolean;
  external_ref: string | null;
  expires_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface NoticeWorkflow {
  workflow_id: string;
  user_id: string;
  source_id: string;
  notice_id: string;
  status: NoticeWorkflowStatus;
  title: string | null;
  deadline: string | null;
  location: string | null;
  audience: string | null;
  materials: string[];
  source_evidence: string[];
  confidence: number;
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
      RunStatus.PAUSED, RunStatus.SUCCEEDED, RunStatus.PARTIAL, RunStatus.FAILED, RunStatus.CANCELLED
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
      AgentEventType.RUN_COMPLETED, AgentEventType.RUN_FAILED, AgentEventType.RUN_CANCELLED,
      AgentEventType.RUN_PAUSED, AgentEventType.RUN_RESUMED, AgentEventType.RUN_RETRIED,
      AgentEventType.RUN_RETRY_SCHEDULED, AgentEventType.RUN_RECOVERY_STARTED,
      AgentEventType.RUN_RECOVERED
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
      AgentErrorCode.AGENT_SOURCE_POLICY_VIOLATION, AgentErrorCode.AGENT_ACADEMIC_POLICY_RESTRICTED,
      AgentErrorCode.AGENT_CAPABILITY_DISABLED, AgentErrorCode.AGENT_RUNTIME_UNAVAILABLE,
      AgentErrorCode.AGENT_CURSOR_INVALID
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
    if (raw.toUpperCase() === 'PENDING') return AdjustmentProposalStatus.PROPOSED;
    const values: string[] = [
      AdjustmentProposalStatus.PROPOSED, AdjustmentProposalStatus.APPROVED,
      AdjustmentProposalStatus.REJECTED, AdjustmentProposalStatus.EXPIRED
    ];
    const normalized: string = raw.toUpperCase();
    return values.indexOf(normalized) >= 0 ? normalized as AdjustmentProposalStatus : AdjustmentProposalStatus.UNKNOWN;
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
      artifact_ids: artifactIds,
      retry_of: raw.retry_of === null || raw.retry_of === undefined ? null : raw.retry_of as string
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
        ? null : raw.latest_run_id as string,
      input_ref: (raw.input_ref ?? {}) as Record<string, Object>
    };
  }

  static studentGoal(raw: Record<string, Object>): StudentGoal {
    return {
      goal_id: (raw.goal_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      name: (raw.name ?? '') as string,
      category: (raw.category ?? '') as string,
      status: (raw.status ?? '') as string,
      target_date: raw.target_date === null || raw.target_date === undefined ? null : raw.target_date as string,
      progress_percent: (raw.progress_percent ?? 0) as number,
      milestone_count: (raw.milestone_count ?? 0) as number,
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string
    };
  }

  static learningPlanSummary(raw: Record<string, Object>): LearningPlanSummary {
    const recommendationsRaw: Object = raw.recommendations ?? [];
    const warningsRaw: Object = raw.warning_codes ?? [];
    return {
      plan_id: (raw.plan_id ?? '') as string,
      goal_id: raw.goal_id === null || raw.goal_id === undefined ? null : raw.goal_id as string,
      status: (raw.status ?? '') as string,
      stage: (raw.stage ?? '') as string,
      headline: (raw.headline ?? '') as string,
      completion_percent: (raw.completion_percent ?? 0) as number,
      planned_item_count: (raw.planned_item_count ?? 0) as number,
      executed_item_count: (raw.executed_item_count ?? 0) as number,
      planned_minutes: (raw.planned_minutes ?? 0) as number,
      next_action: (raw.next_action ?? '') as string,
      recommendations: Array.isArray(recommendationsRaw) ? recommendationsRaw as string[] : [],
      warning_codes: Array.isArray(warningsRaw) ? warningsRaw as string[] : [],
      generated_at: (raw.generated_at ?? '') as string,
      candidate_annotation: AgentDtoParser.candidateAnnotation(raw.candidate_annotation)
    };
  }

  /** 候选模型只读注解：缺失或形状不符时返回 null，页面据此走"不可用"分支。 */
  static candidateAnnotation(raw: Object | undefined | null): CandidateAnnotation | null {
    if (raw === undefined || raw === null || typeof raw !== 'object' || Array.isArray(raw)) return null;
    const record: Record<string, Object> = raw as Record<string, Object>;
    const claimsRaw: Object = record.claim_codes ?? [];
    const summaryValue: Object = record.summary ?? null;
    return {
      available: record.available === true,
      capability_name: (record.capability_name ?? '') as string,
      capability_version: (record.capability_version ?? '') as string,
      reason: record.reason === undefined || record.reason === null ? null : record.reason as string,
      inference_source: (record.inference_source ?? 'DETERMINISTIC_FALLBACK') as string,
      model_key: record.model_key === undefined || record.model_key === null ? null : record.model_key as string,
      model_version: record.model_version === undefined || record.model_version === null ? null : record.model_version as string,
      prompt_version: record.prompt_version === undefined || record.prompt_version === null ? null : record.prompt_version as string,
      input_digest: record.input_digest === undefined || record.input_digest === null ? null : record.input_digest as string,
      shadow_run_id: record.shadow_run_id === undefined || record.shadow_run_id === null ? null : record.shadow_run_id as string,
      used_fallback: record.used_fallback === true,
      claim_codes: Array.isArray(claimsRaw) ? claimsRaw as string[] : [],
      summary: summaryValue === null ? null : summaryValue as string,
      read_only: record.read_only !== false,
      affects_production: record.affects_production === true
    };
  }

  static learnerStateSnapshot(raw: Record<string, Object>): LearnerStateSnapshot {
    const warningsRaw: Object = raw.warning_codes ?? [];
    return {
      snapshot_id: (raw.snapshot_id ?? '') as string,
      state_type: (raw.state_type ?? '') as string,
      confidence: (raw.confidence ?? 0) as number,
      data_quality: (raw.data_quality ?? 'unavailable') as string,
      projection_kind: (raw.projection_kind ?? 'CORE') as string,
      warning_codes: Array.isArray(warningsRaw) ? warningsRaw as string[] : [],
      evidence_count: (raw.evidence_count ?? 0) as number
    };
  }

  static learnerStateSnapshotPage(raw: Record<string, Object>): LearnerStateSnapshotPage {
    const itemsRaw: Object = raw.items ?? [];
    return {
      items: Array.isArray(itemsRaw)
        ? (itemsRaw as Record<string, Object>[]).map((item: Record<string, Object>) => AgentDtoParser.learnerStateSnapshot(item))
        : [],
      total: (raw.total ?? 0) as number
    };
  }

  static forecastSummary(raw: Record<string, Object>): ForecastSummary {
    const limitationsRaw: Object = raw.limitations ?? [];
    const probability: Object = raw.probability ?? null;
    return {
      forecast_id: (raw.forecast_id ?? '') as string,
      forecast_type: (raw.forecast_type ?? '') as string,
      probability: probability === null ? null : probability as number,
      confidence: (raw.confidence ?? 0) as number,
      data_quality: (raw.data_quality ?? 'unavailable') as string,
      horizon_end: raw.horizon_end === undefined || raw.horizon_end === null ? null : raw.horizon_end as string,
      limitations: Array.isArray(limitationsRaw) ? limitationsRaw as string[] : []
    };
  }

  static dataSourceControl(raw: Record<string, Object>): DataSourceControl {
    return {
      source_key: (raw.source_key ?? '') as string,
      status: (raw.status ?? 'ENABLED') as string,
      can_pause: raw.can_pause !== false,
      can_resume: raw.can_resume !== false
    };
  }

  static modelTransparency(raw: Record<string, Object>): ModelTransparency {
    const capabilitiesRaw: Object = raw.capabilities ?? [];
    const capabilities: ModelCapabilityTransparency[] = Array.isArray(capabilitiesRaw)
      ? (capabilitiesRaw as Record<string, Object>[]).map((item: Record<string, Object>) => {
        return {
          capability_name: (item.capability_name ?? '') as string,
          campusmate_lm_status: (item.campusmate_lm_status ?? 'SHADOW_ONLY') as string,
          quality_gate_passed: item.quality_gate_passed === true,
          performance_measured: item.performance_measured === true,
          uses_real_model_inference: item.uses_real_model_inference === true
        };
      })
      : [];
    return {
      capabilities: capabilities,
      campusmate_lm_enabled: raw.campusmate_lm_enabled === true,
      campusmate_lm_affects_production: raw.campusmate_lm_affects_production === true,
      shadow_results_modify_plans: raw.shadow_results_modify_plans === true,
      read_only_canary_active: raw.read_only_canary_active === true,
      real_inference_observed: raw.real_inference_observed === true,
      fixture_only: raw.fixture_only === true
    };
  }

  static adaptiveInterventionOutcome(raw: Record<string, Object>): AdaptiveInterventionOutcome {
    const reasonsRaw: Object = raw.decision_reason_codes ?? [];
    const adjustmentsRaw: Object = raw.suggested_adjustments ?? [];
    const warningsRaw: Object = raw.warning_codes ?? [];
    return {
      intervention_id: (raw.intervention_id ?? '') as string,
      plan_id: raw.plan_id === undefined || raw.plan_id === null ? null : raw.plan_id as string,
      observation_status: (raw.observation_status ?? 'NOT_STARTED') as string,
      execution_signal: (raw.execution_signal ?? 'NOT_STARTED') as string,
      adoption: (raw.adoption ?? 'NOT_STARTED') as string,
      verdict: (raw.verdict ?? 'NOT_OBSERVED') as string,
      observed_outcome: (raw.observed_outcome ?? 'INSUFFICIENT_EVIDENCE') as string,
      causal_claim: (raw.causal_claim ?? 'NOT_ESTIMATED') as string,
      decision: raw.decision === undefined || raw.decision === null ? null : raw.decision as string,
      decision_reason_codes: Array.isArray(reasonsRaw) ? reasonsRaw as string[] : [],
      suggested_adjustments: Array.isArray(adjustmentsRaw) ? adjustmentsRaw as string[] : [],
      decision_status: raw.decision_status === undefined || raw.decision_status === null ? null : raw.decision_status as string,
      observation_due_at: raw.observation_due_at === undefined || raw.observation_due_at === null ? null : raw.observation_due_at as string,
      warning_codes: Array.isArray(warningsRaw) ? warningsRaw as string[] : []
    };
  }

  static adaptiveIntervention(raw: Record<string, Object>): AdaptiveIntervention {
    return {
      intervention_id: (raw.intervention_id ?? '') as string,
      goal_id: (raw.goal_id ?? '') as string,
      plan_id: raw.plan_id === undefined || raw.plan_id === null ? null : raw.plan_id as string,
      status: (raw.status ?? '') as string,
      strategy_code: (raw.strategy_code ?? '') as string,
      data_quality: raw.data_quality === undefined || raw.data_quality === null ? null : raw.data_quality as string,
      observation_due_at: raw.observation_due_at === undefined || raw.observation_due_at === null ? null : raw.observation_due_at as string
    };
  }

  static finalReviewCampaign(raw: Record<string, Object>): FinalReviewCampaign {
    const examIdsRaw: Object = raw.exam_ids ?? [];
    const examIds: string[] = Array.isArray(examIdsRaw) ? examIdsRaw as string[] : [];
    const periodsRaw: Object = raw.preferred_periods ?? [];
    const restDaysRaw: Object = raw.rest_days ?? [];
    return {
      campaign_id: (raw.campaign_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      exam_ids: examIds,
      daily_capacity_minutes: (raw.daily_capacity_minutes ?? 0) as number,
      preferred_periods: Array.isArray(periodsRaw) ? periodsRaw as string[] : [],
      rest_days: Array.isArray(restDaysRaw) ? restDaysRaw as string[] : [],
      intensity: (raw.intensity ?? 'medium') as string,
      status: (raw.status ?? '') as string,
      active_version: raw.active_version === null || raw.active_version === undefined
        ? null : raw.active_version as number,
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string
    };
  }

  static finalReviewDailyItem(raw: Record<string, Object>): FinalReviewDailyItem {
    const status: string = (raw.status ?? '') as string;
    return {
      item_id: (raw.item_id ?? '') as string,
      title: (raw.title ?? '') as string,
      course_name: raw.course_name === null || raw.course_name === undefined ? null : raw.course_name as string,
      scheduled_minutes: (raw.scheduled_minutes ?? 0) as number,
      sort_order: (raw.sort_order ?? 0) as number,
      status: status,
      personal_task_id: raw.personal_task_id === null || raw.personal_task_id === undefined
        ? null : raw.personal_task_id as string,
      difficulty: raw.difficulty === null || raw.difficulty === undefined ? null : raw.difficulty as string,
      completed: status.toLowerCase() === 'completed'
    };
  }

  static finalReviewPlanVersion(raw: Record<string, Object>): FinalReviewPlanVersion {
    return {
      campaign_id: (raw.campaign_id ?? '') as string,
      version: (raw.version ?? 0) as number,
      plan: (raw.plan ?? {}) as Record<string, Object>,
      model_provider: (raw.model_provider ?? '') as string,
      route_policy: (raw.route_policy ?? '') as string,
      risk_level: AgentEnumParser.riskLevel((raw.risk_level ?? '') as string),
      approval_id: raw.approval_id === null || raw.approval_id === undefined ? null : raw.approval_id as string,
      supersedes_version: raw.supersedes_version === null || raw.supersedes_version === undefined
        ? null : raw.supersedes_version as number,
      created_at: (raw.created_at ?? '') as string
    };
  }

  static finalReviewAdjustmentProposal(raw: Record<string, Object>): FinalReviewAdjustmentProposal {
    const proposal: Record<string, Object> = (raw.proposal ?? {}) as Record<string, Object>;
    return {
      proposal_id: (raw.proposal_id ?? '') as string,
      campaign_id: (raw.campaign_id ?? '') as string,
      status: AgentEnumParser.adjustmentProposalStatus((raw.status ?? '') as string),
      source_version: (raw.source_version ?? 0) as number,
      proposal: proposal,
      risk_level: AgentEnumParser.riskLevel((raw.risk_level ?? '') as string),
      approval_id: raw.approval_id === null || raw.approval_id === undefined ? null : raw.approval_id as string,
      target_version: raw.target_version === null || raw.target_version === undefined ? null : raw.target_version as number,
      reason: raw.reason === null || raw.reason === undefined ? null : raw.reason as string,
      summary: (proposal.summary ?? '学习计划调整建议') as string,
      rationale: (proposal.rationale ?? proposal.reason ?? '') as string,
      created_at: (raw.created_at ?? '') as string
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
      session_id: (raw.session_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      question: (raw.question ?? '') as string,
      course_id: raw.course_id === null || raw.course_id === undefined ? null : raw.course_id as string,
      assistance_mode: AgentEnumParser.assistanceMode((raw.assistance_mode ?? '') as string),
      academic_policy: AgentEnumParser.academicPolicy((raw.academic_policy ?? '') as string),
      effective_assistance_mode: AgentEnumParser.assistanceMode(
        (raw.effective_assistance_mode ?? raw.assistance_mode ?? '') as string),
      source_policy: AgentDtoParser.courseSourcePolicy(
        (raw.source_policy ?? {}) as Record<string, Object>),
      status: AgentEnumParser.runStatus((raw.status ?? '') as string),
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string,
      finished_at: raw.finished_at === null || raw.finished_at === undefined ? null : raw.finished_at as string,
      error_code: raw.error_code === null || raw.error_code === undefined ? null : raw.error_code as string,
      artifact_ids: artifactIds,
      fallback_used: (raw.fallback_used ?? false) as boolean
    };
  }

  static courseResearchSource(raw: Record<string, Object>): CourseResearchSource {
    const sourceType: string = (raw.source_type ?? '') as string;
    const verified: boolean = (raw.is_verified ?? false) as boolean;
    const supports: boolean | null = raw.supports_claim === null || raw.supports_claim === undefined
      ? null : raw.supports_claim as boolean;
    let verification: CitationVerification = CitationVerification.PARTIAL;
    if (verified) verification = CitationVerification.VERIFIED;
    if (supports === false || (raw.is_fabricated ?? false) as boolean) verification = CitationVerification.FAILED;
    return {
      source_id: (raw.source_id ?? '') as string,
      source_type: sourceType,
      title: (raw.title ?? '') as string,
      url: raw.url === null || raw.url === undefined ? null : raw.url as string,
      snippet: raw.snippet === null || raw.snippet === undefined ? null : raw.snippet as string,
      source_ref: raw.source_ref === null || raw.source_ref === undefined ? null : raw.source_ref as string,
      accessed_at: (raw.accessed_at ?? '') as string,
      is_verified: verified,
      verification_note: raw.verification_note === null || raw.verification_note === undefined
        ? null : raw.verification_note as string,
      supports_claim: supports,
      is_fabricated: (raw.is_fabricated ?? false) as boolean,
      verification: verification,
      is_course_material: sourceType === 'course_material',
      retrieved_at: (raw.accessed_at ?? '') as string
    };
  }

  static noticeSource(raw: Record<string, Object>): NoticeSource {
    return {
      source_id: (raw.source_id ?? '') as string,
      code: (raw.code ?? '') as string,
      display_name: (raw.display_name ?? '') as string,
      permission_scope: raw.permission_scope === null || raw.permission_scope === undefined
        ? null : raw.permission_scope as string,
      kind: (raw.kind ?? '') as string,
      automation_enabled: (raw.automation_enabled ?? false) as boolean
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
      action_type: (raw.action_type ?? '') as string,
      title: (raw.title ?? '') as string,
      risk_level: AgentEnumParser.riskLevel((raw.risk_level ?? '') as string),
      status: AgentEnumParser.noticeActionStatus((raw.status ?? '') as string),
      materials: materials,
      is_external: (raw.is_external ?? (raw.external_ref !== null && raw.external_ref !== undefined)) as boolean,
      external_ref: raw.external_ref === null || raw.external_ref === undefined ? null : raw.external_ref as string,
      expires_at: raw.expires_at === null || raw.expires_at === undefined ? null : raw.expires_at as string,
      error_code: raw.error_code === null || raw.error_code === undefined ? null : raw.error_code as string,
      error_message: raw.error_message === null || raw.error_message === undefined ? null : raw.error_message as string,
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string
    };
  }

  static noticeWorkflow(raw: Record<string, Object>): NoticeWorkflow {
    const actionsRaw: Object = raw.actions ?? [];
    const actionsArr: Record<string, Object>[] = Array.isArray(actionsRaw) ? actionsRaw as Record<string, Object>[] : [];
    const materialsRaw: Object = raw.materials ?? [];
    const evidenceRaw: Object = raw.source_evidence ?? [];
    return {
      workflow_id: (raw.workflow_id ?? '') as string,
      user_id: (raw.user_id ?? '') as string,
      source_id: (raw.source_id ?? '') as string,
      notice_id: (raw.notice_id ?? '') as string,
      status: AgentEnumParser.noticeWorkflowStatus((raw.status ?? '') as string),
      title: raw.title === null || raw.title === undefined ? null : raw.title as string,
      deadline: raw.deadline === null || raw.deadline === undefined ? null : raw.deadline as string,
      location: raw.location === null || raw.location === undefined ? null : raw.location as string,
      audience: raw.audience === null || raw.audience === undefined ? null : raw.audience as string,
      materials: Array.isArray(materialsRaw) ? materialsRaw as string[] : [],
      source_evidence: Array.isArray(evidenceRaw) ? evidenceRaw as string[] : [],
      confidence: (raw.confidence ?? 0) as number,
      uncertainty: {
        missing_fields: Array.isArray(raw.uncertainty) ? raw.uncertainty as string[] : [],
        confidence: `${raw.confidence ?? 0}`,
        notes: Array.isArray(raw.uncertainty) ? (raw.uncertainty as string[]).join('、') : ''
      },
      actions: actionsArr.map((action: Record<string, Object>) => AgentDtoParser.noticeWorkflowAction(action)),
      created_at: (raw.created_at ?? '') as string,
      updated_at: (raw.updated_at ?? '') as string
    };
  }
}
