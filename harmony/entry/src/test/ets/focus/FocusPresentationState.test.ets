import { describe, expect, it } from '@ohos/hypium';
import {
  FocusCountdownRunToken,
  FocusPresentationState,
  FocusSessionActionGate
} from '../../../main/ets/features/focus/FocusPresentationState';

export default function focusPresentationStateTest(): void {
  describe('FocusPresentationState', () => {
    it('moves the lobby from duration selection through mode selection to confirmation', 0, () => {
      expect(FocusPresentationState.nextLobbyStep('ASK_DURATION')).assertEqual('ASK_MODE');
      expect(FocusPresentationState.nextLobbyStep('ASK_MODE')).assertEqual('CONFIRM');
    });

    it('formats a completed sixty-five-second session for the summary hero', 0, () => {
      expect(FocusPresentationState.formatDuration(65)).assertEqual('1 分 05 秒');
    });

    it('clamps custom durations to the supported focus range', 0, () => {
      expect(FocusPresentationState.durationSeconds(45)).assertEqual(2700);
      expect(FocusPresentationState.durationSeconds(4)).assertEqual(300);
      expect(FocusPresentationState.durationSeconds(300)).assertEqual(14400);
    });

    it('shows local observation only for a focus-mode session with a status', 0, () => {
      expect(FocusPresentationState.shouldShowObservation('focus', 'active', 'SMART_GUARD')).assertTrue();
      expect(FocusPresentationState.shouldShowObservation('focus', 'active', 'QUIET')).assertFalse();
      expect(FocusPresentationState.shouldShowObservation('short_break', 'active', 'SMART_GUARD')).assertFalse();
      expect(FocusPresentationState.shouldShowObservation('focus', '', 'SMART_GUARD')).assertFalse();
    });

    it('allows only one focus action until the current action completes', 0, () => {
      const gate: FocusSessionActionGate = new FocusSessionActionGate();
      expect(gate.tryStart()).assertTrue();
      expect(gate.tryStart()).assertFalse();
      gate.complete();
      expect(gate.tryStart()).assertTrue();
    });

    it('invalidates a pending lobby countdown when the page leaves', 0, () => {
      const token: FocusCountdownRunToken = new FocusCountdownRunToken();
      const pending: number = token.begin();
      expect(token.isCurrent(pending)).assertTrue();
      token.cancel();
      expect(token.isCurrent(pending)).assertFalse();
    });

    it('maps companion phases to a robot state and accessible status text', 0, () => {
      expect(FocusPresentationState.robotStateForVoice('LISTENING')).assertEqual('LISTENING');
      expect(FocusPresentationState.robotStateForVoice('SPEAKING')).assertEqual('SPEAKING');
      expect(FocusPresentationState.robotStatusText('THINKING')).assertEqual('让我想想');
    });
  });
}
