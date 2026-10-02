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
const { BehaviorV34Label } = loadService(resolve(serviceDirectory, 'BehaviorV34Decision.ets'));

function fakeModel(logits) {
  return {
    getInputs: () => [{ setData() {} }],
    predict: async () => [{ elementNum: logits.length, getData: () => new Float32Array(logits).buffer }]
  };
}

test('V3.2 fallback drops all prior TSM evidence and requires eight fresh V3.4 frames', async () => {
  const provider = new MindSporeBehaviorProvider({});
  provider.activeRun = provider.runToken.begin();
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
  assert.equal(fallback.modelVersion, 'V3.4');
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
});
