import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import test from 'node:test';

import { InMemoryReplayStore, verifyServiceAssertion } from '../src/serviceAssertion.ts';

const secret = 'shared-secret';

function base64url(value) {
  return Buffer.from(value).toString('base64url');
}

function fixtureToken(overrides = {}) {
  const payload = {
    iss: 'campusmate-backend',
    aud: 'openmaic-service',
    sub: 'u1',
    course_id: 'c1',
    scope: ['stage:read'],
    iat: 100,
    exp: 160,
    jti: 'once',
    ...overrides,
  };
  const header = base64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = base64url(JSON.stringify(payload));
  const signature = createHmac('sha256', secret).update(`${header}.${body}`).digest('base64url');
  return `${header}.${body}.${signature}`;
}

test('accepts a valid course-scoped assertion', () => {
  const claims = verifyServiceAssertion(fixtureToken(), 'c1', ['stage:read'], 100, {
    secret,
    replayStore: new InMemoryReplayStore(),
  });
  assert.equal(claims.sub, 'u1');
  assert.deepEqual(claims.scope, ['stage:read']);
});

test('rejects a replayed jti', () => {
  const replayStore = new InMemoryReplayStore();
  const token = fixtureToken();
  verifyServiceAssertion(token, 'c1', ['stage:read'], 100, { secret, replayStore });
  assert.throws(
    () => verifyServiceAssertion(token, 'c1', ['stage:read'], 100, { secret, replayStore }),
    /replay/i,
  );
});

test('rejects expiry, course mismatch, missing scope and tampering', () => {
  const options = { secret, replayStore: new InMemoryReplayStore() };
  assert.throws(() => verifyServiceAssertion(fixtureToken({ exp: 100 }), 'c1', ['stage:read'], 100, options), /expired/i);
  assert.throws(() => verifyServiceAssertion(fixtureToken({ jti: 'course' }), 'c2', ['stage:read'], 100, options), /course/i);
  assert.throws(() => verifyServiceAssertion(fixtureToken({ jti: 'scope', scope: [] }), 'c1', ['stage:read'], 100, options), /scope/i);
  assert.throws(() => verifyServiceAssertion(`${fixtureToken()}x`, 'c1', ['stage:read'], 100, options), /signature/i);
});
