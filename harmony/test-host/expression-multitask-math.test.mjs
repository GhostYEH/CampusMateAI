import assert from 'node:assert/strict';
import test from 'node:test';
import { ExpressionModelMath } from '../entry/src/main/ets/service/ExpressionModelMath.ts';
import { ExpressionStateConfidenceWindow } from '../entry/src/main/ets/service/ExpressionStateConfidenceWindow.ts';
import { ExpressionFaceTrackContinuity } from '../entry/src/main/ets/service/ExpressionFaceTrackContinuity.ts';

const calibration = {
  expression_temperature: 2,
  state_scales: [1, 0.5, 2],
  state_biases: [0, 1, -1]
};

test('expression probabilities apply temperature to seven logits and remain normalized', () => {
  const prediction = ExpressionModelMath.decode(new Float32Array([0, 0, 0, 0, 0, 4, 0]), 2);
  assert.equal(prediction.label, 'sad');
  assert.ok(prediction.confidence > 0.54 && prediction.confidence < 0.56);
  assert.ok(Math.abs(prediction.probabilities.reduce((sum, value) => sum + value, 0) - 1) < 1e-12);
  assert.equal(ExpressionModelMath.decode(new Float32Array([0, 1]), 2), undefined);
  assert.equal(ExpressionModelMath.decode(new Float32Array([0, 1, 2, 3, 4, 5, 6]), 0), undefined);
});

test('independent state heads use per-state scale and bias sigmoid calibration', () => {
  const states = ExpressionModelMath.calibrateStates([0, 2, 1], calibration);
  assert.ok(Math.abs(states.boredom - 0.5) < 1e-12);
  assert.ok(Math.abs(states.confusion - (1 / (1 + Math.exp(-2)))) < 1e-12);
  assert.ok(Math.abs(states.frustration - (1 / (1 + Math.exp(-1)))) < 1e-12);
});

test('state confidence waits for four frames, averages logits, then calibrates', () => {
  const window = new ExpressionStateConfidenceWindow(4, 5000, calibration);
  assert.equal(window.push([0, 0, 0], 1000), undefined);
  assert.equal(window.push([2, 0, 0], 1450), undefined);
  assert.equal(window.push([4, 0, 0], 1900), undefined);
  const states = window.push([6, 0, 0], 2350);
  assert.ok(Math.abs(states.boredom - (1 / (1 + Math.exp(-3)))) < 1e-12);
  assert.equal(window.sampleCount(), 4);
});

test('invalid, out-of-order, or stale windows clear and require four new samples', () => {
  const window = new ExpressionStateConfidenceWindow(4, 1000, calibration);
  window.push([1, 1, 1], 1000);
  window.push([1, 1, 1], 1200);
  window.push([1, 1, 1], 1400);
  assert.equal(window.push([1, 1, 1], 2600), undefined);
  assert.equal(window.sampleCount(), 1);
  assert.equal(window.push([1, 1, 1], 2500), undefined);
  assert.equal(window.sampleCount(), 1);
  assert.equal(window.latest(4000), undefined);
  assert.equal(window.sampleCount(), 0);
  assert.equal(window.push([Number.NaN, 0, 0], 4100), undefined);
  assert.equal(window.sampleCount(), 0);
});

test('face-box continuity accepts nearby motion and rejects abrupt track changes', () => {
  const previous = { left: 100, top: 80, width: 100, height: 100 };
  assert.equal(ExpressionFaceTrackContinuity.isSameTrack(previous,
    { left: 110, top: 82, width: 98, height: 101 }, 640, 480), true);
  assert.equal(ExpressionFaceTrackContinuity.isSameTrack(previous,
    { left: 420, top: 80, width: 100, height: 100 }, 640, 480), false);
});
