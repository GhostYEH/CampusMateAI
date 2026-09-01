import { http } from '@kit.NetworkKit';
import { ApiClient } from '../data/ApiClient';
import { FocusMode, StudyBehaviorSummary, StudyDailyGoal, StudySession, StudySessionCreate, StudySessionFinish } from '../data/Models';

interface StudyGoalUpdateRequest {
  target_minutes: number;
}

export class StudyRepository {
  private readonly client: ApiClient;

  constructor(client: ApiClient) {
    this.client = client;
  }

  async listSessions(): Promise<StudySession[]> {
    return this.client.request<StudySession[]>(http.RequestMethod.GET, 'study/sessions?page=1&page_size=20');
  }

  async activeSession(): Promise<StudySession | undefined> {
    return this.client.requestOptional<StudySession>(http.RequestMethod.GET, 'study/sessions/active');
  }

  async dailyGoal(): Promise<StudyDailyGoal> {
    return this.client.request<StudyDailyGoal>(http.RequestMethod.GET, 'study/goals/daily');
  }

  async updateDailyGoal(targetMinutes: number): Promise<StudyDailyGoal> {
    const request: StudyGoalUpdateRequest = { target_minutes: targetMinutes };
    return this.client.request<StudyDailyGoal>(http.RequestMethod.PUT, 'study/goals/daily', request);
  }

  async start(mode: FocusMode, goal?: string, relatedTaskId?: string): Promise<StudySession> {
    const payload: StudySessionCreate = { mode: mode, goal: goal, related_task_id: relatedTaskId };
    return this.client.request<StudySession>(http.RequestMethod.POST, 'study/sessions', payload);
  }

  async pause(id: string): Promise<StudySession> {
    return this.client.request<StudySession>(http.RequestMethod.POST, `study/sessions/${id}/pause`);
  }

  async resume(id: string): Promise<StudySession> {
    return this.client.request<StudySession>(http.RequestMethod.POST, `study/sessions/${id}/resume`);
  }

  async finish(id: string, report?: string, behaviorSummary?: StudyBehaviorSummary): Promise<StudySession> {
    const body: StudySessionFinish = { self_report: report, behavior_summary: behaviorSummary };
    return this.client.request<StudySession>(http.RequestMethod.POST, `study/sessions/${id}/finish`, body);
  }
}
