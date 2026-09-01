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
  FocusCameraSignalPresentation,
  FocusBehaviorLabelText,
  FrameAnalysisGate,
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

    it('runs camera assistance only during a study focus interval', 0, () => {
      expect(FocusCameraActivationPolicy.shouldRun('focus')).assertTrue();
      expect(FocusCameraActivationPolicy.shouldRun('short_break')).assertFalse();
      expect(FocusCameraActivationPolicy.shouldRun('long_break')).assertFalse();
    });

    it('starts only for focus session starts and focus resumes', 0, () => {
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'focus'))
        .assertEqual(FocusCameraLifecycleAction.START);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'short_break'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'long_break'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'focus'))
        .assertEqual(FocusCameraLifecycleAction.START);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'short_break'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'long_break'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
    });

    it('stops for pause finish hide leave and mode reset', 0, () => {
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.PAUSE, 'focus'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.FINISH, 'focus'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.HIDE, 'focus'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.LEAVE, 'focus'))
        .assertEqual(FocusCameraLifecycleAction.STOP);
      expect(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESET, 'focus'))
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
