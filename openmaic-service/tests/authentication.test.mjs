import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { courseScopedRoute, createHarness, mintAssertion, withServer } from './helpers.mjs';

const FIXED_NOW = 1_700_000_000;

async function expectStatus(baseUrl, path, token, expected) {
  const headers = token === null ? {} : { 'x-campusmate-service-assertion': token };
  const response = await fetch(`${baseUrl}${path}`, { headers });
  assert.equal(response.status, expected, `expected ${expected} for ${path}`);
  return response.json();
}

test('rejects a request without an assertion header', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', null, 401);
  });
  harness.database.close();
});

test('rejects a tampered signature', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', `${token}x`, 401);
  });
  harness.database.close();
});

test('rejects an assertion signed with the wrong secret', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1', secret: 'other' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', token, 401);
  });
  harness.database.close();
});

test('rejects a foreign issuer or audience', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const foreignIssuer = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1', issuer: 'someone-else' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', foreignIssuer, 401);
    const foreignAudience = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1', audience: 'other-service' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', foreignAudience, 401);
  });
  harness.database.close();
});

test('rejects expired, future-issued and over-long assertions', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const expired = mintAssertion({ iat: FIXED_NOW - 120, ttl: 60, scopes: ['workspace:read'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', expired, 401);

    const future = mintAssertion({ iat: FIXED_NOW + 30, ttl: 60, scopes: ['workspace:read'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', future, 401);

    const tooLong = mintAssertion({ iat: FIXED_NOW, ttl: 61, scopes: ['workspace:read'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', tooLong, 401);

    const atLimit = mintAssertion({ iat: FIXED_NOW, ttl: 60, scopes: ['workspace:read'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', atLimit, 200);
  });
  harness.database.close();
});

test('binds an assertion to exactly one course', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-2/workspaces', token, 403);

    const own = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', own, 200);
  });
  harness.database.close();
});

test('rejects an assertion that lacks the required scope', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['something:else'], courseId: 'course-1' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', token, 403);
  });
  harness.database.close();
});

test('readiness needs the service:status scope, not just a valid assertion', async () => {
  const harness = createHarness({ now: () => FIXED_NOW });
  await withServer(harness.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'] });
    await expectStatus(baseUrl, '/internal/health/ready', token, 403);

    const scoped = mintAssertion({ iat: FIXED_NOW, scopes: ['service:status'] });
    await expectStatus(baseUrl, '/internal/health/ready', scoped, 200);
  });
  harness.database.close();
});

test('rejects a replayed jti within the same process', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1', jti: 'single-use' });
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', token, 200);
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', token, 401);
  });
  harness.database.close();
});

test('keeps replay protection across a service restart', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'openmaic-replay-'));
  const path = join(directory, 'service.db');
  const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1', jti: 'durable' });

  const first = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()], database: new ServiceDatabase(path) });
  await withServer(first.server, async (baseUrl) => {
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', token, 200);
  });
  first.database.close();

  // A fresh process must still remember that the jti was spent.
  const second = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()], database: new ServiceDatabase(path) });
  await withServer(second.server, async (baseUrl) => {
    await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', token, 401);
  });
  second.database.close();
});

test('never echoes the assertion, the secret or an internal address', async () => {
  const harness = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()] });
  await withServer(harness.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1' });
    const bodies = [
      await expectStatus(baseUrl, '/internal/courses/course-2/workspaces', token, 403),
      await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', `${token}tampered`, 401),
      await expectStatus(baseUrl, '/internal/courses/course-1/workspaces', null, 401),
    ];
    for (const body of bodies) {
      const text = JSON.stringify(body);
      assert.equal(text.includes('test-secret'), false, 'leaked the shared secret');
      assert.equal(text.includes('eyJ'), false, 'leaked assertion material');
      assert.equal(text.includes('127.0.0.1'), false, 'leaked an internal address');
      assert.equal(text.includes('openmaic-service'), false, 'leaked the internal audience');
      assert.deepEqual(Object.keys(body), ['error']);
    }
  });
  harness.database.close();
});

test('consumes the jti and the handler write in one transaction', async () => {
  const harness = createHarness({ now: () => FIXED_NOW });
  const rows = harness.database.raw.prepare('SELECT count(*) AS total FROM consumed_service_assertions').get();
  assert.equal(Number(rows.total), 0);

  let observedDuringHandler = -1;
  const failing = createHarness({
    now: () => FIXED_NOW,
    routes: [
      courseScopedRoute(() => {
        observedDuringHandler = Number(
          harness.database.raw.prepare('SELECT count(*) AS total FROM consumed_service_assertions').get().total,
        );
        throw new Error('handler failed');
      }),
    ],
    database: harness.database,
  });

  await withServer(failing.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1', jti: 'rollback' });
    const response = await fetch(`${baseUrl}/internal/courses/course-1/workspaces`, {
      headers: { 'x-campusmate-service-assertion': token },
    });
    assert.equal(response.status, 500);
  });

  // The handler runs inside the transaction, so it already sees the consumed jti.
  assert.equal(observedDuringHandler, 1);
  // Its failure rolled that consumption back, so the assertion was never spent.
  const after = harness.database.raw.prepare('SELECT count(*) AS total FROM consumed_service_assertions').get();
  assert.equal(Number(after.total), 0);

  // The same token therefore still works once the handler stops failing.
  const healthy = createHarness({ now: () => FIXED_NOW, routes: [courseScopedRoute()], database: harness.database });
  await withServer(healthy.server, async (baseUrl) => {
    const token = mintAssertion({ iat: FIXED_NOW, scopes: ['workspace:read'], courseId: 'course-1', jti: 'rollback' });
    const response = await fetch(`${baseUrl}/internal/courses/course-1/workspaces`, {
      headers: { 'x-campusmate-service-assertion': token },
    });
    assert.equal(response.status, 200);
  });
  harness.database.close();
});
