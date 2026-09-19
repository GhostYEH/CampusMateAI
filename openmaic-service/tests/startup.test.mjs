import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createHmac, randomUUID } from 'node:crypto';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { normalizeCapabilities } from '../src/capabilities.ts';
import { createArchiveRoutes } from '../src/archive/routes.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { createDiscoveryRoutes } from '../src/discovery/routes.ts';
import { createEditorRoutes } from '../src/editor/routes.ts';
import { createMaterialRoutes } from '../src/material/routes.ts';
import { createPlayerRoutes } from '../src/player/routes.ts';
import { createJobRoutes } from '../src/jobs/routes.ts';
import { createGenerationRoutes } from '../src/generation/routes.ts';
import { createWhiteboardRoutes } from '../src/whiteboard/routes.ts';
import { createProviderRoutes } from '../src/provider/routes.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';

const main = fileURLToPath(new URL('../src/main.ts', import.meta.url));
const node = process.execPath;
const SECRET = 'startup-test-secret';

function startService(env) {
  return spawnSync(node, ['--experimental-strip-types', main], {
    encoding: 'utf8',
    timeout: 20_000,
    env: { ...process.env, ...env },
  });
}

function mintAssertion(scopes) {
  const iat = Math.floor(Date.now() / 1000);
  const payload = {
    iss: 'campusmate-backend',
    aud: 'openmaic-service',
    sub: 'startup-user',
    course_id: 'startup-course',
    scope: scopes,
    iat,
    exp: iat + 60,
    jti: randomUUID(),
  };
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  return `${header}.${body}.${createHmac('sha256', SECRET).update(`${header}.${body}`).digest('base64url')}`;
}

test('refuses to start without an internal secret', () => {
  const result = startService({ OPENMAIC_INTERNAL_SECRET: '', OPENMAIC_DATABASE_URL: ':memory:' });
  assert.notEqual(result.status, 0);
  assert.match(`${result.stdout}${result.stderr}`, /OPENMAIC_INTERNAL_SECRET is required/);
});

test('refuses to start without a database location', () => {
  const result = startService({ OPENMAIC_INTERNAL_SECRET: SECRET, OPENMAIC_DATABASE_URL: '' });
  assert.notEqual(result.status, 0);
  assert.match(`${result.stdout}${result.stderr}`, /OPENMAIC_DATABASE_URL is required/);
});

test('comes up on a complete configuration and serves authenticated readiness', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'openmaic-startup-'));
  const port = 4399;
  const child = spawn(node, ['--experimental-strip-types', main], {
    env: {
      ...process.env,
      OPENMAIC_INTERNAL_SECRET: SECRET,
      OPENMAIC_DATABASE_URL: join(directory, 'service.db'),
      OPENMAIC_HOST: '127.0.0.1',
      OPENMAIC_PORT: String(port),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stderr = '';
  child.stderr.on('data', (chunk) => {
    stderr += String(chunk);
  });

  try {
    let up = false;
    for (let attempt = 0; attempt < 60 && !up; attempt += 1) {
      try {
        up = (await fetch(`http://127.0.0.1:${port}/internal/health/live`)).ok;
      } catch {
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
    }
    assert.ok(up, `service did not start: ${stderr}`);

    const anonymous = await fetch(`http://127.0.0.1:${port}/internal/health/ready`);
    assert.equal(anonymous.status, 401);

    const wrongScope = await fetch(`http://127.0.0.1:${port}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': mintAssertion(['workspace:read']) },
    });
    assert.equal(wrongScope.status, 403);

    const ready = await fetch(`http://127.0.0.1:${port}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': mintAssertion(['service:status']) },
    });
    assert.equal(ready.status, 200, await ready.clone().text());
    const payload = await ready.json();
    assert.equal(payload.status, 'ready');
    assert.equal(payload.dependencies.database, true);
    // The advertised set is exactly what the mounted route modules declare —
    // derived here from the same factories `main.ts` mounts, so this can fail
    // only when the running service and the route table disagree.
    const mounted = new ServiceDatabase(':memory:');
    const declared = normalizeCapabilities([
      ...createWorkspaceRoutes({ database: mounted }),
      ...createDiscoveryRoutes({ database: mounted }),
      ...createArchiveRoutes({ database: mounted }),
      ...createEditorRoutes({ database: mounted }),
      ...createMaterialRoutes({ database: mounted }),
      ...createPlayerRoutes({ database: mounted }),
      ...createJobRoutes({ database: mounted }),
      ...createGenerationRoutes({ database: mounted }),
      ...createWhiteboardRoutes({ database: mounted }),
      ...createProviderRoutes({ database: mounted }),
    ].flatMap((route) => route.capabilities));
    mounted.close();
    assert.deepEqual(payload.capabilities, declared);
    assert.ok(payload.capabilities.includes('workspace'));
    assert.ok(payload.capabilities.includes('folder'));
    assert.ok(payload.capabilities.includes('search'));
    assert.ok(payload.capabilities.includes('editor'));
    assert.ok(payload.capabilities.includes('player'));
    assert.ok(payload.capabilities.includes('material'));
    assert.ok(payload.capabilities.includes('export-maic'));
    assert.ok(payload.capabilities.includes('import-maic'));

    // The database survives a restart, so the replay guard must too.
    const replayToken = mintAssertion(['service:status']);
    const first = await fetch(`http://127.0.0.1:${port}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': replayToken },
    });
    const second = await fetch(`http://127.0.0.1:${port}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': replayToken },
    });
    assert.equal(first.status, 200);
    assert.equal(second.status, 401);
  } finally {
    child.kill();
  }
});
