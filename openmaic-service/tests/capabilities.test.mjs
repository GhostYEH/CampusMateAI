import assert from 'node:assert/strict';
import test from 'node:test';

import { isKnownCapability, KNOWN_CAPABILITIES, normalizeCapabilities } from '../src/capabilities.ts';

test('exposes a frozen, duplicate-free vocabulary', () => {
  assert.ok(KNOWN_CAPABILITIES.length > 0);
  assert.equal(new Set(KNOWN_CAPABILITIES).size, KNOWN_CAPABILITIES.length);
  assert.ok(KNOWN_CAPABILITIES.includes('workspace'));
  assert.ok(KNOWN_CAPABILITIES.includes('export-video'));
});

test('drops anything outside the vocabulary', () => {
  assert.deepEqual(normalizeCapabilities(['workspace', 'rm -rf /', 'editor', '']), ['workspace', 'editor']);
  assert.deepEqual(normalizeCapabilities(['WORKSPACE', 'Workspace']), []);
  assert.deepEqual(normalizeCapabilities([null, 42, {}, undefined]), []);
  assert.equal(isKnownCapability('workspace'), true);
  assert.equal(isKnownCapability('not-a-capability'), false);
});

test('returns a stable order regardless of input order', () => {
  const first = normalizeCapabilities(['tts', 'workspace', 'player']);
  const second = normalizeCapabilities(['player', 'workspace', 'tts']);
  assert.deepEqual(first, second);
  assert.deepEqual(first, KNOWN_CAPABILITIES.filter((capability) => first.includes(capability)));
});

test('de-duplicates repeated declarations', () => {
  assert.deepEqual(normalizeCapabilities(['workspace', 'workspace', 'workspace']), ['workspace']);
});
