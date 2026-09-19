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

test('caps the assertion lifetime', () => {
  const options = { secret, replayStore: new InMemoryReplayStore() };
  // 60s is the documented maximum; one second more must be refused.
  assert.throws(
    () => verifyServiceAssertion(fixtureToken({ jti: 'long', iat: 100, exp: 161 }), 'c1', ['stage:read'], 100, options),
    /lifetime/i,
  );
  assert.equal(
    verifyServiceAssertion(fixtureToken({ jti: 'at-limit', iat: 100, exp: 160 }), 'c1', ['stage:read'], 100, options).jti,
    'at-limit',
  );
});

test('skips the course comparison for a route that is not course-scoped', () => {
  const options = { secret, replayStore: new InMemoryReplayStore() };
  const claims = verifyServiceAssertion(fixtureToken({ jti: 'unscoped' }), null, ['stage:read'], 100, options);
  assert.equal(claims.course_id, 'c1');
});

test('exposes a machine-readable failure code without leaking material', () => {
  const options = { secret, replayStore: new InMemoryReplayStore() };
  const cases = [
    [fixtureToken({ exp: 100 }), 'assertion_expired'],
    [fixtureToken({ jti: 'code-course' }), 'assertion_course'],
    [fixtureToken({ jti: 'code-scope', scope: [] }), 'assertion_scope'],
    [`${fixtureToken({ jti: 'code-sig' })}x`, 'assertion_signature'],
  ];
  for (const [token, expectedCode] of cases) {
    const course = expectedCode === 'assertion_course' ? 'c2' : 'c1';
    try {
      verifyServiceAssertion(token, course, ['stage:read'], 100, options);
      assert.fail(`expected ${expectedCode}`);
    } catch (error) {
      assert.equal(error.code, expectedCode);
      assert.equal(error.message.includes(secret), false);
    }
  }
});
