import assert from 'node:assert/strict';
import test from 'node:test';

import { createServer } from '../src/server.ts';

async function withServer(server, fn) {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { port } = server.address();
    return await fn(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
  }
}

test('reports dependency failure without exposing a public UI', async () => {
  const app = createServer({ readiness: async () => ({ database: false }) });
  await withServer(app, async (baseUrl) => {
    const ready = await fetch(`${baseUrl}/internal/health/ready`);
    assert.equal(ready.status, 503);
    assert.deepEqual(await ready.json(), {
      status: 'degraded',
      dependencies: { database: false },
    });

    const root = await fetch(`${baseUrl}/`);
    assert.equal(root.status, 404);
  });
});

test('returns live status without checking optional dependencies', async () => {
  const app = createServer({ readiness: async () => ({ database: false }) });
  await withServer(app, async (baseUrl) => {
    const live = await fetch(`${baseUrl}/internal/health/live`);
    assert.equal(live.status, 200);
    assert.deepEqual(await live.json(), { status: 'ok' });
  });
});
