import assert from 'node:assert/strict';
import test from 'node:test';

import { createHarness, mintAssertion, withServer } from './helpers.mjs';

test('serves liveness anonymously without touching dependencies', async () => {
  const harness = createHarness({ readiness: () => ({ database: false }) });
  await withServer(harness.server, async (baseUrl) => {
    const live = await fetch(`${baseUrl}/internal/health/live`);
    assert.equal(live.status, 200);
    assert.deepEqual(await live.json(), { status: 'ok' });
  });
  harness.database.close();
});

test('refuses readiness without an assertion', async () => {
  const harness = createHarness();
  await withServer(harness.server, async (baseUrl) => {
    const ready = await fetch(`${baseUrl}/internal/health/ready`);
    assert.equal(ready.status, 401);
    assert.deepEqual(await ready.json(), { error: 'unauthorized' });
  });
  harness.database.close();
});

test('reports ready with the real capability set when dependencies are healthy', async () => {
  const harness = createHarness({ routes: [], readiness: () => ({ runtime: true, database: true }) });
  await withServer(harness.server, async (baseUrl) => {
    const ready = await fetch(`${baseUrl}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': mintAssertion() },
    });
    assert.equal(ready.status, 200);
    const payload = await ready.json();
    assert.equal(payload.status, 'ready');
    assert.equal(payload.reason, 'ready');
    assert.deepEqual(payload.dependencies, { runtime: true, database: true });
    // No content capability is implemented yet, so none may be advertised.
    assert.deepEqual(payload.capabilities, []);
  });
  harness.database.close();
});

test('reports degraded with a safe reason and no capabilities when a dependency is down', async () => {
  const harness = createHarness({ readiness: () => ({ runtime: true, database: false }) });
  await withServer(harness.server, async (baseUrl) => {
    const ready = await fetch(`${baseUrl}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': mintAssertion() },
    });
    assert.equal(ready.status, 503);
    const payload = await ready.json();
    assert.equal(payload.status, 'degraded');
    assert.equal(payload.reason, 'dependency_unavailable');
    assert.deepEqual(payload.capabilities, []);
  });
  harness.database.close();
});

test('advertises exactly the capabilities declared by mounted routes', async () => {
  const harness = createHarness({
    routes: [
      {
        method: 'GET',
        pattern: '/internal/things',
        scopes: ['thing:read'],
        courseScoped: false,
        capabilities: ['workspace', 'not-a-real-capability'],
        handler: () => ({ status: 200, body: { ok: true } }),
      },
    ],
  });
  await withServer(harness.server, async (baseUrl) => {
    const ready = await fetch(`${baseUrl}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': mintAssertion() },
    });
    const payload = await ready.json();
    assert.deepEqual(payload.capabilities, ['workspace']);
  });
  harness.database.close();
});

test('exposes no public surface', async () => {
  const harness = createHarness();
  await withServer(harness.server, async (baseUrl) => {
    const root = await fetch(`${baseUrl}/`);
    assert.equal(root.status, 404);
    assert.deepEqual(await root.json(), { error: 'not_found' });
  });
  harness.database.close();
});

test('requires authentication before revealing whether an internal path exists', async () => {
  const harness = createHarness();
  await withServer(harness.server, async (baseUrl) => {
    const anonymous = await fetch(`${baseUrl}/internal/does-not-exist`);
    assert.equal(anonymous.status, 401);

    const authenticated = await fetch(`${baseUrl}/internal/does-not-exist`, {
      headers: { 'x-campusmate-service-assertion': mintAssertion({ scopes: [] }) },
    });
    assert.equal(authenticated.status, 404);
  });
  harness.database.close();
});

test('rejects a non-GET request to the liveness probe', async () => {
  const harness = createHarness();
  await withServer(harness.server, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/internal/health/live`, { method: 'POST' });
    assert.equal(response.status, 405);
    assert.deepEqual(await response.json(), { error: 'method_not_allowed' });
  });
  harness.database.close();
});
