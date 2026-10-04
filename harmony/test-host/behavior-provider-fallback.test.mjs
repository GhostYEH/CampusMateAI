import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';

// Exercise the real ArkTS provider orchestration with fake tensors, without a device or SDK.
const modules = new Map();
function loadService(path) {
  if (modules.has(path)) return modules.get(path);
  const scope = { Float32Array, Uint8Array, ArrayBuffer, Date, Number, Math };
  let source = readFileSync(path, 'utf8');
  source = source.replace(/import\s*\{([\s\S]*?)\}\s*from\s*'([^']+)';/g, (_, names, reference) => {
    let imported = {};
    if (reference.startsWith('.')) {
      const base = resolve(dirname(path), reference);
      imported = loadService(existsSync(`${base}.ets`) ? `${base}.ets` : `${base}.ts`);
    }
    for (const name of names.split(',').map(value => value.trim()).filter(Boolean)) {
      scope[name] = imported[name];
    }
    return '';
  });
  const exports = [...source.matchAll(/export\s+(?:class|enum|const|function)\s+(\w+)/g)]
    .map(match => match[1]);
  const javascript = stripTypeScriptTypes(source.replace(/\bexport\s+/g, ''), { mode: 'transform' });
  const result = runInNewContext(`${javascript}\n({${exports.join(',')}})`, scope, { filename: path });
  modules.set(path, result);
  return result;
}

const serviceDirectory = fileURLToPath(new URL('../entry/src/main/ets/service/', import.meta.url));
const { MindSporeBehaviorProvider } = loadService(resolve(serviceDirectory, 'MindSporeBehaviorProvider.ets'));
const { BehaviorV34Label, BehaviorV34Decision } = loadService(resolve(serviceDirectory, 'BehaviorV34Decision.ets'));
const { BehaviorRuntimeModel } = loadService(resolve(serviceDirectory, 'BehaviorModelSelection.ets'));
const { BehaviorHybridPolicy } = loadService(resolve(serviceDirectory, 'BehaviorHybridPolicy.ets'));
const { BehaviorPredictionTemporalSmoother } = loadService(
  resolve(serviceDirectory, 'BehaviorPredictionTemporalSmoother.ets'));

function singleResult(read, phone, label, isStable = true) {
  return { label, isStable, confidence: Math.max(read, phone), margin: Math.abs(read - phone),
    probabilities: [read, 0, phone, 0] };
}

test('a phone spike abstains until smoothed evidence supports the accepted phone label', () => {
  const smoother = new BehaviorPredictionTemporalSmoother();
  smoother.smoothResult(singleResult(0.9, 0.1, BehaviorV34Label.READ), BehaviorV34Decision.MODEL_STATE);
  const spike = smoother.smoothResult(singleResult(0.1, 0.9, BehaviorV34Label.PHONE_INTERACTION),
    BehaviorV34Decision.MODEL_STATE);
  assert.equal(spike.label, BehaviorV34Label.CONTINUE_OBSERVING);
  assert.equal(spike.isStable, false);
  assert.ok(Math.abs(spike.confidence - 0.62) < 1e-6);
  assert.ok(Math.abs(spike.margin - 0.24) < 1e-6);
  let sustained;
  for (let index = 0; index < 5; index++) {
    sustained = smoother.smoothResult(singleResult(0.1, 0.9, BehaviorV34Label.PHONE_INTERACTION),
      BehaviorV34Decision.MODEL_STATE);
  }
  assert.equal(sustained.label, BehaviorV34Label.PHONE_INTERACTION);
  assert.equal(sustained.confidence, sustained.probabilities[2]);
});

test('smoothed near ties and rejected raw evidence remain uncertain', () => {
  const smoother = new BehaviorPredictionTemporalSmoother();
  smoother.smoothResult(singleResult(0.7, 0.3, BehaviorV34Label.READ), BehaviorV34Decision.MODEL_STATE);
  const nearTie = smoother.smoothResult(singleResult(0.1, 0.9, BehaviorV34Label.PHONE_INTERACTION),
    BehaviorV34Decision.MODEL_STATE);
  assert.equal(nearTie.isStable, false);
  assert.ok(nearTie.margin < 0.05);
  smoother.reset();
  smoother.smoothResult(singleResult(0.1, 0.9, BehaviorV34Label.PHONE_INTERACTION), BehaviorV34Decision.MODEL_STATE);
  assert.equal(smoother.smoothResult(singleResult(0.4, 0.6,
    BehaviorV34Label.CONTINUE_OBSERVING, false), BehaviorV34Decision.MODEL_STATE).isStable, false);
});

test('smoothing preserves hybrid writing and computer restrictions', () => {
  const smoother = new BehaviorPredictionTemporalSmoother();
  const writingBlocked = smoother.smoothResult({ label: BehaviorV34Label.READ, isStable: true,
    confidence: 0.4, margin: 0.3, probabilities: [0.4, 0.5, 0.1, 0, 0] }, BehaviorHybridPolicy.MODEL_STATE);
  assert.equal(writingBlocked.label, BehaviorV34Label.CONTINUE_OBSERVING);
  smoother.reset();
  smoother.smoothResult({ label: BehaviorV34Label.COMPUTER, isStable: true,
    confidence: 0.9, margin: 0.8, probabilities: [0.1, 0, 0, 0.9, 0] }, BehaviorHybridPolicy.MODEL_STATE);
  const noConfirmation = smoother.smoothResult({ label: BehaviorV34Label.READ, isStable: true,
    confidence: 0.9, margin: 0.8, probabilities: [0.9, 0, 0, 0, 0.1] }, BehaviorHybridPolicy.MODEL_STATE);
  assert.equal(noConfirmation.label, BehaviorV34Label.CONTINUE_OBSERVING);
});

test('legacy decisions bypass calibrated rejection and use a separate history', () => {
  const smoother = new BehaviorPredictionTemporalSmoother();
  const visible = { label: BehaviorV34Label.READ, isStable: true,
    confidence: 0.9, margin: 0.8, probabilities: [0.9, 0, 0, 0.1] };
  const idle = { label: BehaviorV34Label.NO_VISIBLE_STUDY, isStable: true,
    confidence: 0.9, margin: 0.8, probabilities: [0.1, 0, 0, 0.9] };
  smoother.smoothResult(visible, BehaviorRuntimeModel.V32);
  const legacy = smoother.smoothResult(idle, BehaviorRuntimeModel.V32);
  assert.equal(legacy.label, BehaviorV34Label.READ);
  assert.equal(legacy.isStable, true);
  assert.ok(Math.abs(legacy.probabilities[0] - 0.62) < 1e-6);
  assert.equal(legacy.confidence, legacy.probabilities[0]);
  const calibrated = smoother.smoothResult(idle, BehaviorV34Decision.MODEL_STATE);
  assert.equal(calibrated.label, BehaviorV34Label.NO_VISIBLE_STUDY);
  assert.equal(calibrated.probabilities[3], 0.9);
});

test('provider signals and reminders consume the smoothed decision', async () => {
  const provider = new MindSporeBehaviorProvider({});
  provider.activeRun = provider.runToken.begin();
  provider.model = fakeModel([20, 0, 0, 0]);
  const frame = { width: 4, height: 4, pixels: new Uint8Array(4 * 4 * 4), timestamp: 1000,
    personBox: { left: 0, top: 0, right: 4, bottom: 4 } };
  const reading = await provider.analyze(frame);
  assert.equal(reading.label, BehaviorV34Label.READ);
  provider.model = fakeModel([0, 0, 20, 0]);
  const spike = await provider.analyze({ ...frame, timestamp: 1500 });
  assert.equal(spike.isStable, false);
  assert.equal(spike.label, BehaviorV34Label.CONTINUE_OBSERVING);
  assert.equal(provider.reminderTracker.phoneSince, -1);
  let sustained;
  for (let index = 0; index < 6; index++) {
    sustained = await provider.analyze({ ...frame, timestamp: 2000 + index * 500 });
  }
  assert.equal(sustained.label, BehaviorV34Label.PHONE_INTERACTION);
  assert.ok(sustained.confidence > spike.confidence);
});

test('V3.2 and V3.4 keep separate smoothing histories despite both having four mapped probabilities', async () => {
  const provider = new MindSporeBehaviorProvider({});
  provider.activeRun = provider.runToken.begin();
  provider.model = fakeModel([20, 0, 0, 0]);
  provider.v32Model = fakeModel([20, 0]);
  const frame = { width: 4, height: 4, pixels: new Uint8Array(4 * 4 * 4), timestamp: 1000,
    personBox: { left: 0, top: 0, right: 0, bottom: 0 } };
  assert.equal((await provider.analyze(frame)).label, BehaviorV34Label.NO_VISIBLE_STUDY);
  const resumed = await provider.analyze({ ...frame, timestamp: 1500,
    personBox: { left: 0, top: 0, right: 4, bottom: 4 } });
  assert.equal(resumed.label, BehaviorV34Label.READ);
  assert.ok(resumed.confidence > 0.9);
});

test('V3.2 fallback follows the smoothed argmax without calibrated agreement rejection', async () => {
  const provider = new MindSporeBehaviorProvider({});
  provider.activeRun = provider.runToken.begin();
  provider.v32Model = fakeModel([0, 10]);
  const frame = { width: 4, height: 4, pixels: new Uint8Array(4 * 4 * 4), timestamp: 1000,
    personBox: { left: 0, top: 0, right: 0, bottom: 0 } };
  assert.equal((await provider.analyze(frame)).label, BehaviorV34Label.READ);
  provider.v32Model = fakeModel([10, 0]);
  const spike = await provider.analyze({ ...frame, timestamp: 1500 });
  assert.equal(spike.label, BehaviorV34Label.READ);
  assert.equal(spike.isStable, true);
  let idle;
  for (let index = 0; index < 5; index++) {
    idle = await provider.analyze({ ...frame, timestamp: 2000 + index * 500 });
  }
  assert.equal(idle.label, BehaviorV34Label.NO_VISIBLE_STUDY);
  assert.equal(idle.isStable, true);
  assert.equal(idle.modelVersion, 'V3.2');
  assert.match(provider.detail(), /V3\.2/);
});

for (const failure of ['throws', 'wrong output shape', 'nonfinite output']) {
  test(`a V3.4 frame that ${failure} clears EMA before the next successful frame`, async () => {
    const provider = new MindSporeBehaviorProvider({});
    provider.activeRun = provider.runToken.begin();
    provider.model = fakeModel([20, 0, 0, 0]);
    const frame = { width: 4, height: 4, pixels: new Uint8Array(4 * 4 * 4), timestamp: 1000,
      personBox: { left: 0, top: 0, right: 4, bottom: 4 } };
    assert.equal((await provider.analyze(frame)).label, BehaviorV34Label.READ);
    provider.model = failure === 'throws' ? {
      ...fakeModel([]), predict: async () => { throw new Error('inference failed'); }
    } : fakeModel(failure === 'wrong output shape' ? [0, 20] : [0, 0, Number.NaN, 0]);
    assert.equal(await provider.analyze({ ...frame, timestamp: 1500 }), undefined);
    assert.equal(provider.latestSignal(), undefined);
    assert.equal(provider.currentReminder(), '');
    provider.model = fakeModel([0, 0, 20, 0]);
    const recovered = await provider.analyze({ ...frame, timestamp: 2000 });
    assert.equal(recovered.label, BehaviorV34Label.PHONE_INTERACTION);
    assert.equal(recovered.isStable, true);
    assert.ok(recovered.confidence > 0.9);
    assert.equal(recovered.modelVersion, 'V3.4');
  });
}

test('TSM inference failure removes temporal evidence and reports the V3.4 classifier', async () => {
  const provider = new MindSporeBehaviorProvider({});
  provider.activeRun = provider.runToken.begin();
  provider.model = fakeModel([20, 0, 0, 0]);
  let temporalCalled = false;
  provider.temporalModel = {
    ...fakeModel([], [1, 8, 3, 224, 224]),
    predict: async () => { temporalCalled = true; throw new Error('temporal inference failed'); }
  };
  for (let index = 0; index < 7; index++) provider.temporalFrames.push(new Float32Array(3 * 224 * 224));
  const frame = { width: 4, height: 4, pixels: new Uint8Array(4 * 4 * 4), timestamp: 4000,
    personBox: { left: 0, top: 0, right: 4, bottom: 4 } };
  const degraded = await provider.analyze(frame);
  assert.equal(temporalCalled, true);
  assert.equal(degraded.modelVersion, 'V3.4');
  assert.equal(degraded.label, BehaviorV34Label.READ);
  assert.equal(provider.cachedTemporal, undefined);
  assert.equal(provider.temporalModel, null);
});

function fakeModel(logits, shape = [1, 3, 224, 224]) {
  return {
    getInputs: () => [{ shape, elementNum: shape.reduce((size, dimension) => size * dimension, 1), setData() {} }],
    predict: async () => [{ elementNum: logits.length, getData: () => new Float32Array(logits).buffer }]
  };
}

test('V3.2 fallback drops all prior TSM evidence and requires eight fresh V3.4 frames', async () => {
  const provider = new MindSporeBehaviorProvider({});
  provider.activeRun = provider.runToken.begin();
  provider.resetSessionSummary(10_000);
  provider.model = fakeModel([0, 0, 0, 20]);
  provider.v32Model = fakeModel([0, 10]);
  provider.temporalModel = fakeModel([0, 0, 0, 10, 0]);
  provider.cachedTemporal = {
    label: BehaviorV34Label.COMPUTER, confidence: 0.99, isStable: true,
    margin: 0.98, probabilities: [0.0025, 0.0025, 0.0025, 0.99, 0.0025]
  };
  provider.computerConfirmationCount = 2;
  provider.lastTemporalAtMs = 10_000;
  for (let index = 0; index < 8; index++) provider.temporalFrames.push(new Float32Array(3 * 224 * 224));
  const frame = {
    width: 4, height: 4, pixels: new Uint8Array(4 * 4 * 4), timestamp: 10_500,
    personBox: { left: 0, top: 0, right: 0, bottom: 0 }
  };
  const fallback = await provider.analyze(frame);
  assert.equal(fallback.modelVersion, 'V3.2');
  assert.equal(provider.sessionSummary().model_version, 'V3.2');
  assert.equal(provider.cachedTemporal, undefined);
  assert.equal(provider.computerConfirmationCount, 0);
  assert.equal(provider.temporalFrames.size(), 0);
  assert.equal(provider.lastTemporalAtMs, 0);

  const resumed = await provider.analyze({
    ...frame, timestamp: 11_000, personBox: { left: 0, top: 0, right: 4, bottom: 4 }
  });
  assert.equal(resumed.modelVersion, 'V3.4');
  assert.notEqual(resumed.label, BehaviorV34Label.COMPUTER);
  assert.equal(provider.temporalFrames.size(), 1);
  assert.equal(provider.cachedTemporal, undefined);
  assert.equal(provider.sessionSummary().model_version, 'V3.4');
  await provider.stop();
  assert.equal(provider.sessionSummary().model_version, 'V3.4');
});
