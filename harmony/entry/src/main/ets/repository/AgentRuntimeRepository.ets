import { ApiClient } from '../data/ApiClient';
import { http } from '@kit.NetworkKit';
import { AgentEvent, AgentRun, CourseResearchResult, NoticeWorkflow } from '../data/AgentRuntimeModels';

export class AgentRuntimeRepository {
  constructor(private readonly api: ApiClient) {}

  async capabilities(): Promise<Record<string, Object>> { return await this.api.request<Record<string, Object>>(http.RequestMethod.GET, 'agent-runtime/capabilities'); }
  async getRun(runId: string): Promise<AgentRun> { return await this.api.request<AgentRun>(http.RequestMethod.GET, `agent-runs/${encodeURIComponent(runId)}`); }
  async getEvents(runId: string, afterEventId?: string): Promise<{ items: AgentEvent[] }> {
    const suffix: string = afterEventId ? `?after_event_id=${encodeURIComponent(afterEventId)}` : '';
    return await this.api.request<{ items: AgentEvent[] }>(http.RequestMethod.GET, `agent-runs/${encodeURIComponent(runId)}/events${suffix}`);
  }
  async createResearch(key: string, payload: Record<string, Object>): Promise<CourseResearchResult> {
    return await this.api.request<CourseResearchResult>(http.RequestMethod.POST, 'course-research/sessions', payload);
  }
  async analyzeNotice(noticeId: string): Promise<NoticeWorkflow> { return await this.api.request<NoticeWorkflow>(http.RequestMethod.POST, `notices/${encodeURIComponent(noticeId)}/workflow`); }
}
