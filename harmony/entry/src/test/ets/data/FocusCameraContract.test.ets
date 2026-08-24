import { describe, expect, it } from '@ohos/hypium';
import {
  DetectionCandidate,
  FocusCameraState,
  FocusCameraStateText,
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
    });

    it('drops throttled and in-flight frames', 0, () => {
      const gate = new FrameAnalysisGate(1000);
      expect(gate.tryAcquire(1000)).assertTrue();
      expect(gate.tryAcquire(2500)).assertFalse();
      gate.release();
      expect(gate.tryAcquire(1999)).assertFalse();
      expect(gate.tryAcquire(2000)).assertTrue();
    });

    it('keeps unavailable camera states explicit and non-punitive', 0, () => {
      expect(FocusCameraStateText.describe(FocusCameraState.WAITING_FOR_PERSON))
        .assertEqual('相机已启用，等待检测到学生人体');
      expect(FocusCameraStateText.describe(FocusCameraState.PERMISSION_DENIED))
        .assertEqual('未获得相机权限，行为提醒已停用');
    });
  });
}
