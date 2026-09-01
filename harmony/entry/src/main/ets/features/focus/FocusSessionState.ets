import { StudySession } from '../../data/Models';

export class FocusSessionState {
  static remainingSeconds(session: StudySession, nowEpochMillis: number,
    fallbackPlannedSeconds: number = 0): number {
    const plannedSeconds: number = Math.max(0,
      session.planned_duration_seconds ?? fallbackPlannedSeconds);
    if (plannedSeconds === 0) return 0;
    const startedAt: number = Date.parse(session.started_at);
    if (isNaN(startedAt)) return plannedSeconds;
    const endedAt: number = session.status === 'paused' && session.paused_at !== undefined ? Date.parse(session.paused_at) : nowEpochMillis;
    const safeEndedAt: number = isNaN(endedAt) ? nowEpochMillis : endedAt;
    const elapsedSeconds: number = Math.max(0, Math.floor((safeEndedAt - startedAt) / 1000) - Math.max(0, session.pause_seconds));
    return Math.max(0, plannedSeconds - elapsedSeconds);
  }

  static shouldRunClock(session: StudySession | undefined): boolean {
    return session !== undefined && session.status === 'active';
  }

  static completedSeconds(session: StudySession, nowEpochMillis: number): number {
    const planned: number = Math.max(0, session.planned_duration_seconds ?? 0);
    return Math.max(0, planned - FocusSessionState.remainingSeconds(session, nowEpochMillis));
  }
}
