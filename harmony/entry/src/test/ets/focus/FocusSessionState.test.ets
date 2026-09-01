import { describe, expect, it } from '@ohos/hypium';
import { FocusSessionState } from '../../../main/ets/features/focus/FocusSessionState';
import { StudySession } from '../../../main/ets/data/Models';

export default function focusSessionStateTest(): void {
  describe('FocusSessionState', () => {
    it('derives remaining seconds from server timestamps and persisted pause time', 0, () => {
      const session: StudySession = {
        id: 'focus-1', mode: 'focus', started_at: '2026-09-02T00:00:00.000Z',
        duration_seconds: 0, pause_seconds: 120, status: 'active', planned_duration_seconds: 1500
      };
      expect(FocusSessionState.remainingSeconds(session, Date.parse('2026-09-02T00:05:00.000Z'))).assertEqual(1320);
    });

    it('keeps a paused session frozen at the moment it was paused', 0, () => {
      const session: StudySession = {
        id: 'focus-2', mode: 'focus', started_at: '2026-09-02T00:00:00.000Z',
        paused_at: '2026-09-02T00:05:00.000Z', duration_seconds: 0, pause_seconds: 0,
        status: 'paused', planned_duration_seconds: 1500
      };
      expect(FocusSessionState.remainingSeconds(session, Date.parse('2026-09-02T00:20:00.000Z'))).assertEqual(1200);
    });
  });
}
