import { describe, expect, it } from '@ohos/hypium';
import {
  DetectionCandidate,
  FocusCameraState,
  FocusCameraStateText,
  FocusCameraRunToken,
  FocusCameraActivationPolicy,
  FocusCameraLifecycleEvent,
  FocusCameraLifecycleAction,
  FocusCameraLifecyclePolicy,
  FocusSessionModeRecovery,
  FocusCameraSignalPresentation,
  FocusBehaviorLabelText,
  FrameAnalysisGate,
  PersonAbsenceTracker,
  PersonRoiSelector
} from '../../../main/ets/service/FocusCameraContract';

function candidate(label: number, score: number, left: number, top: number,
  width: number, height: number): DetectionCandidate {
  return { labels: [label], score: score, boundingBox: { left, top, width, height } };
}

export default function focusCameraContractTest(): void {
  describe('FocusCameraContract', () => {
    it('selects the highest-confidence person and clamps its box', 0, () => {
      const selected = PersonRoiSelector.select([
        candidate(13, 0.61, 40, 30, 50, 60),
        candidate(13, 0.92, -4, 5, 120, 110),
        candidate(2, 0.99, 0, 0, 200, 200)
      ], 100, 80);
      expect(selected?.left).assertEqual(0);
      expect(selected?.top).assertEqual(5);
      expect(selected?.right).assertEqual(100);
      expect(selected?.bottom).assertEqual(80);
    });

    it('rejects non-person and low-confidence detections', 0, () => {
      expect(PersonRoiSelector.select([
        candidate(8, 0.95, 0, 0, 90, 70),
        candidate(13, 0.49, 0, 0, 90, 70)
      ], 100, 80)).assertUndefined();
      expect(PersonRoiSelector.select([
        candidate(13, Number.NaN, 0, 0, 90, 70),
        candidate(13, 0.90, Number.NaN, 0, 90, 70)
      ], 100, 80)).assertUndefined();
    });

    it('runs camera assistance only for smart-guard focus intervals', 0, () => {
      expect(FocusCameraActivationPolicy.shouldRun('focus', 'SMART_GUARD')).assertTrue();
      expect(FocusCameraActivationPolicy.shouldRun('focus', 'QUIET')).assertFalse();
      expect(FocusCameraActivationPolicy.shouldRun('focus', 'AI_COMPANION')).assertFalse();
      expect(FocusCameraActivationPolicy.shouldRun('short_break', 'SMART_GUARD')).assertFalse();
      expect(FocusCameraActivationPolicy.shouldRun('long_break', 'SMART_GUARD')).assertFalse();
    });

    it('starts only for focus session starts and focus resumes', 0, () => {
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'focus', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.START);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'focus', 'QUIET'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'short_break', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'long_break', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'focus', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.START);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'short_break', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'long_break', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
    });

    it('recovers only supported persisted experience modes', 0, () => {
      expect(FocusSessionModeRecovery.normalize('SMART_GUARD')).assertEqual('SMART_GUARD');
      expect(FocusSessionModeRecovery.normalize('AI_COMPANION')).assertEqual('AI_COMPANION');
      expect(FocusSessionModeRecovery.normalize(undefined)).assertEqual('QUIET');
      expect(FocusSessionModeRecovery.normalize('invalid')).assertEqual('QUIET');
    });

    it('resets the session aggregate for a new focus but not for resume', 0, () => {
      expect(FocusCameraLifecyclePolicy.shouldResetSummary(FocusCameraLifecycleEvent.START, 'focus')).assertTrue();
      expect(FocusCameraLifecyclePolicy.shouldResetSummary(FocusCameraLifecycleEvent.START, 'short_break')).assertFalse();
      expect(FocusCameraLifecyclePolicy.shouldResetSummary(FocusCameraLifecycleEvent.RESUME, 'focus')).assertFalse();
      expect(FocusCameraLifecyclePolicy.shouldResetSummary(FocusCameraLifecycleEvent.HIDE, 'focus')).assertFalse();
    });

    it('resumes from foreground only for an active focus session', 0, () => {
      expect(FocusCameraLifecyclePolicy.shouldResumeOnForeground('active', 'focus', 'SMART_GUARD')).assertTrue();
      expect(FocusCameraLifecyclePolicy.shouldResumeOnForeground('active', 'focus', 'QUIET')).assertFalse();
      expect(FocusCameraLifecyclePolicy.shouldResumeOnForeground('paused', 'focus', 'SMART_GUARD')).assertFalse();
      expect(FocusCameraLifecyclePolicy.shouldResumeOnForeground('completed', 'focus', 'SMART_GUARD')).assertFalse();
      expect(FocusCameraLifecyclePolicy.shouldResumeOnForeground('active', 'short_break', 'SMART_GUARD')).assertFalse();
      expect(FocusCameraLifecyclePolicy.shouldResumeOnForeground('active', 'long_break', 'SMART_GUARD')).assertFalse();
    });

    it('stops for pause finish hide leave and mode reset', 0, () => {
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.PAUSE, 'focus', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.FINISH, 'focus', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.HIDE, 'focus', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.LEAVE, 'focus', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESET, 'focus', 'SMART_GUARD'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
    });

    it('drops throttled and in-flight frames', 0, () => {
      const gate = new FrameAnalysisGate(1000);
      expect(gate.tryAcquire(1000)).assertTrue();
      expect(gate.tryAcquire(2500)).assertFalse();
      gate.release();
      expect(gate.tryAcquire(1999)).assertFalse();
      expect(gate.tryAcquire(2000)).assertTrue();
    });

    it('admits a new frame after the default 500 ms cadence', 0, () => {
      const gate = new FrameAnalysisGate();
      expect(gate.tryAcquire(1000)).assertTrue();
      gate.release();
      expect(gate.tryAcquire(1499)).assertFalse();
      expect(gate.tryAcquire(1500)).assertTrue();
    });

    it('confirms one absence only after the person is missing for five seconds', 0, () => {
      const tracker = new PersonAbsenceTracker();
      expect(tracker.process(false, 1000)).assertFalse();
      expect(tracker.process(false, 5999)).assertFalse();
      expect(tracker.process(false, 6000)).assertTrue();
      expect(tracker.process(false, 9000)).assertFalse();
    });

    it('rearms absence counting after the person returns', 0, () => {
      const tracker = new PersonAbsenceTracker();
      tracker.process(false, 1000);
      expect(tracker.process(false, 6000)).assertTrue();
      expect(tracker.process(true, 6500)).assertFalse();
      expect(tracker.process(true, 7499)).assertFalse();
      expect(tracker.process(false, 8000)).assertFalse();
      expect(tracker.process(false, 14000)).assertFalse();
      expect(tracker.process(true, 15000)).assertFalse();
      expect(tracker.process(true, 16000)).assertFalse();
      expect(tracker.process(false, 17000)).assertFalse();
      expect(tracker.process(false, 22000)).assertTrue();
    });

    it('discards an unfinished absence when camera observation stops', 0, () => {
      const tracker = new PersonAbsenceTracker();
      tracker.process(false, 1000);
      tracker.suspend();
      expect(tracker.process(false, 5000)).assertFalse();
      expect(tracker.process(false, 9999)).assertFalse();
      expect(tracker.process(false, 10000)).assertTrue();
    });

    it('preserves a confirmed absence across suspension until sustained recovery', 0, () => {
      const tracker = new PersonAbsenceTracker();
      tracker.process(false, 1000);
      expect(tracker.process(false, 6000)).assertTrue();
      tracker.suspend();
      expect(tracker.process(false, 12000)).assertFalse();
      expect(tracker.process(false, 18000)).assertFalse();
      expect(tracker.process(true, 19000)).assertFalse();
      expect(tracker.process(true, 20000)).assertFalse();
      expect(tracker.process(false, 21000)).assertFalse();
      expect(tracker.process(false, 26000)).assertTrue();
    });

    it('does not present rejected behavior output as stable', 0, () => {
      expect(FocusCameraSignalPresentation.label('READ', false)).assertEqual('');
      expect(FocusCameraSignalPresentation.confidence(0.91, false)).assertEqual(0);
      expect(FocusCameraSignalPresentation.label('READ', true)).assertEqual('READ');
      expect(FocusCameraSignalPresentation.confidence(0.91, true)).assertEqual(0.91);
      expect(FocusCameraSignalPresentation.shouldPresent(true, FocusCameraState.RUNNING)).assertTrue();
      expect(FocusCameraSignalPresentation.shouldPresent(true, FocusCameraState.WAITING_FOR_PERSON)).assertFalse();
      expect(FocusCameraSignalPresentation.shouldPresent(true, FocusCameraState.STOPPED)).assertFalse();
    });

    it('displays the hybrid computer behavior with a user-facing label', 0, () => {
      expect(FocusBehaviorLabelText.describe('COMPUTER')).assertEqual('使用电脑');
    });

    it('keeps unavailable camera states explicit and non-punitive', 0, () => {
      expect(FocusCameraStateText.describe(FocusCameraState.WAITING_FOR_PERSON))
        .assertEqual('相机已启用，等待检测到学生人体');
      expect(FocusCameraStateText.describe(FocusCameraState.PERMISSION_DENIED))
        .assertEqual('未获得相机权限，行为提醒已停用');
    });

    it('cancels a pending camera start when focus stops', 0, () => {
      const token = new FocusCameraRunToken();
      const pending: number = token.beginStart();
      expect(token.isCurrent(pending)).assertTrue();
      token.stop();
      expect(token.isCurrent(pending)).assertFalse();
    });
  });
}
