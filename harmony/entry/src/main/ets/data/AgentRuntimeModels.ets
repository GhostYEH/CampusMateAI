export type AgentRisk = 'AUTO_SAFE' | 'CONFIRM_REQUIRED' | 'MANUAL_ONLY' | 'UNKNOWN';
export type AgentStatus = 'QUEUED' | 'RUNNING' | 'AWAITING_APPROVAL' | 'SUCCEEDED' | 'PARTIAL' | 'FAILED' | 'CANCELLED' | 'UNKNOWN';

export interface AgentProgress { current: number; total: number; percent: number; }
export interface AgentRun { run_id: string; job_id: string; domain: string; status: AgentStatus; phase: string; current_role?: string; progress: AgentProgress; }
export interface AgentEvent { id: string; type: string; run_id: string; sequence: number; status: AgentStatus; phase: string; role?: string; summary: string; progress: AgentProgress; }
export interface ResearchSource { source_id: string; source_type: string; safe_label: string; verification_status: string; }
export interface CourseResearchResult { research_id: string; effective_mode: string; academic_policy: string; status: string; roles: string[]; warning_codes: string[]; report_summary: string; sources: ResearchSource[]; }
export interface NoticeWorkflow { workflow_id: string; notice_id: string; status: string; source_code: string; source_revision: number; action_risk: AgentRisk; automation_enabled: boolean; }

export function parseAgentStatus(value: string): AgentStatus {
  const known: AgentStatus[] = ['QUEUED', 'RUNNING', 'AWAITING_APPROVAL', 'SUCCEEDED', 'PARTIAL', 'FAILED', 'CANCELLED'];
  return known.indexOf(value as AgentStatus) >= 0 ? value as AgentStatus : 'UNKNOWN';
}

export function parseAgentRisk(value: string): AgentRisk {
  const known: AgentRisk[] = ['AUTO_SAFE', 'CONFIRM_REQUIRED', 'MANUAL_ONLY'];
  return known.indexOf(value as AgentRisk) >= 0 ? value as AgentRisk : 'UNKNOWN';
}
