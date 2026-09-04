import assert from 'node:assert/strict';
import test from 'node:test';
import {
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
  ImageArrivalGate,
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
  assert.equal(FocusCameraActivationPolicy.shouldRun('focus', 'SMART_GUARD'), true);
  assert.equal(FocusCameraActivationPolicy.shouldRun('focus', 'QUIET'), false);
  assert.equal(FocusCameraActivationPolicy.shouldRun('short_break', 'SMART_GUARD'), false);
  assert.equal(FocusCameraActivationPolicy.shouldRun('long_break', 'SMART_GUARD'), false);
});

test('starts only for focus session starts and focus resumes', () => {
  assert.equal(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'focus', 'SMART_GUARD'),
    FocusCameraLifecycleAction.START);
  assert.equal(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'short_break', 'SMART_GUARD'),
    FocusCameraLifecycleAction.STOP);
  assert.equal(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.START, 'long_break', 'SMART_GUARD'),
    FocusCameraLifecycleAction.STOP);
  assert.equal(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'focus', 'SMART_GUARD'),
    FocusCameraLifecycleAction.START);
  assert.equal(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'short_break', 'SMART_GUARD'),
    FocusCameraLifecycleAction.STOP);
  assert.equal(FocusCameraLifecyclePolicy.action(FocusCameraLifecycleEvent.RESUME, 'long_break', 'SMART_GUARD'),
    FocusCameraLifecycleAction.STOP);
});

test('stops for pause, finish, hide, leave, and mode reset', () => {
  for (const event of [
    FocusCameraLifecycleEvent.PAUSE,
    FocusCameraLifecycleEvent.FINISH,
    FocusCameraLifecycleEvent.HIDE,
    FocusCameraLifecycleEvent.LEAVE,
    FocusCameraLifecycleEvent.RESET
  ]) {
    assert.equal(FocusCameraLifecyclePolicy.action(event, 'focus', 'SMART_GUARD'), FocusCameraLifecycleAction.STOP);
  }
});

test('restores only a supported persisted experience mode', () => {
  assert.equal(FocusSessionModeRecovery.normalize('SMART_GUARD'), 'SMART_GUARD');
  assert.equal(FocusSessionModeRecovery.normalize('AI_COMPANION'), 'AI_COMPANION');
  assert.equal(FocusSessionModeRecovery.normalize(undefined), 'QUIET');
  assert.equal(FocusSessionModeRecovery.normalize('unsupported'), 'QUIET');
});

test('drops frames while analysis is running and before the next interval', () => {
  const gate = new FrameAnalysisGate(1000);
  assert.equal(gate.tryAcquire(1000), true);
  assert.equal(gate.tryAcquire(2500), false);
  gate.release();
  assert.equal(gate.tryAcquire(1999), false);
  assert.equal(gate.tryAcquire(2000), true);
});

test('serializes image receiver reads while a frame is being acquired', () => {
  const gate = new ImageArrivalGate();
  assert.equal(gate.tryAcquire(), true);
  assert.equal(gate.tryAcquire(), false);
  gate.release();
  assert.equal(gate.tryAcquire(), true);
});

test('admits a new frame after the default 500 ms cadence', () => {
  const gate = new FrameAnalysisGate();
  assert.equal(gate.tryAcquire(1000), true);
  gate.release();
  assert.equal(gate.tryAcquire(1499), false);
  assert.equal(gate.tryAcquire(1500), true);
});

test('does not present rejected behavior output as stable', () => {
  assert.equal(FocusCameraSignalPresentation.label('READ', false), '');
  assert.equal(FocusCameraSignalPresentation.confidence(0.91, false), 0);
  assert.equal(FocusCameraSignalPresentation.label('READ', true), 'READ');
  assert.equal(FocusCameraSignalPresentation.confidence(0.91, true), 0.91);
  assert.equal(FocusCameraSignalPresentation.shouldPresent(true, FocusCameraState.RUNNING), true);
  assert.equal(FocusCameraSignalPresentation.shouldPresent(true, FocusCameraState.WAITING_FOR_PERSON), false);
  assert.equal(FocusCameraSignalPresentation.shouldPresent(true, FocusCameraState.STOPPED), false);
});

test('displays the hybrid computer behavior with a user-facing label', () => {
  assert.equal(FocusBehaviorLabelText.describe('COMPUTER'), '使用电脑');
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
