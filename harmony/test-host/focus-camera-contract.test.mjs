import assert from 'node:assert/strict';
import test from 'node:test';
import {
  FocusCameraState,
  FocusCameraStateText,
  FocusCameraRunToken,
  FocusCameraActivationPolicy,
  FrameAnalysisGate,
  PersonRoiSelector
} from '../entry/src/main/ets/service/FocusCameraContract.ts';

function candidate(label, score, left, top, width, height) {
  return { labels: [label], score, boundingBox: { left, top, width, height } };
}

test('selects the highest-confidence person and clamps its box', () => {
  const selected = PersonRoiSelector.select([
    candidate(13, 0.61, 40, 30, 50, 60),
    candidate(13, 0.92, -4, 5, 120, 110),
    candidate(2, 0.99, 0, 0, 200, 200)
  ], 100, 80);
  assert.deepEqual(selected, { left: 0, top: 5, right: 100, bottom: 80 });
});

test('rejects non-person, low-confidence, and degenerate detections', () => {
  assert.equal(PersonRoiSelector.select([
    candidate(8, 0.95, 0, 0, 90, 70),
    candidate(13, 0.49, 0, 0, 90, 70),
    candidate(13, 0.90, 20, 20, 0, 10)
  ], 100, 80), undefined);
  assert.equal(PersonRoiSelector.select([
    candidate(13, Number.NaN, 0, 0, 90, 70),
    candidate(13, 0.90, Number.NaN, 0, 90, 70)
  ], 100, 80), undefined);
});

test('enables the camera only for a study focus interval', () => {
  assert.equal(FocusCameraActivationPolicy.shouldRun('focus'), true);
  assert.equal(FocusCameraActivationPolicy.shouldRun('short_break'), false);
  assert.equal(FocusCameraActivationPolicy.shouldRun('long_break'), false);
});

test('drops frames while analysis is running and before the next interval', () => {
  const gate = new FrameAnalysisGate(1000);
  assert.equal(gate.tryAcquire(1000), true);
  assert.equal(gate.tryAcquire(2500), false);
  gate.release();
  assert.equal(gate.tryAcquire(1999), false);
  assert.equal(gate.tryAcquire(2000), true);
});

test('reports safe user-facing states when a frame cannot be analyzed', () => {
  assert.equal(FocusCameraStateText.describe(FocusCameraState.WAITING_FOR_PERSON),
    '相机已启用，等待检测到学生人体');
  assert.equal(FocusCameraStateText.describe(FocusCameraState.PERMISSION_DENIED),
    '未获得相机权限，行为提醒已停用');
  assert.equal(FocusCameraStateText.describe(FocusCameraState.STOPPED),
    '开始专注后启用本地学习状态辅助');
});

test('invalidates an in-progress start when stop is requested', () => {
  const token = new FocusCameraRunToken();
  const firstStart = token.beginStart();
  assert.equal(token.isCurrent(firstStart), true);
  token.stop();
  assert.equal(token.isCurrent(firstStart), false);
  const resumedStart = token.beginStart();
  assert.equal(token.isCurrent(resumedStart), true);
  assert.equal(token.desired(), true);
});
