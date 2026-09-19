import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer as createHttpServer } from 'node:http';

import { ConfigError, loadConfig } from '../src/config.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { createDiscussionRoutes } from '../src/discussion/routes.ts';
import { createGenerationRoutes } from '../src/generation/routes.ts';
import { buildGeneratedStage } from '../src/generation/generator.ts';
import { createJobRoutes } from '../src/jobs/routes.ts';
import { createProviderJobWorker } from '../src/provider/worker.ts';
import { createTtsRoutes } from '../src/tts/routes.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';
import { JobRepository } from '../src/jobs/repository.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const BASE_ENV = { OPENMAIC_INTERNAL_SECRET: 'secret', OPENMAIC_DATABASE_URL: ':memory:' };

function providerStubConfig(baseUrl, extra = {}) {
  return { baseUrl, apiKey: 'stub-key', model: 'stub-model', timeoutMs: 5000, ...extra };
}

function tinyWav() {
  const buffer = Buffer.alloc(256);
  buffer.write('RIFF', 0, 'ascii');
  buffer.write('WAVE', 8, 'ascii');
  return buffer;
}

function chatPayload(content) {
  return JSON.stringify({ choices: [{ message: { content } }] });
}

function audioPayload(wav) {
  return JSON.stringify({ choices: [{ message: { audio: { data: wav.toString('base64') } } }] });
}

async function startStub(handler) {
  const server = createHttpServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  return { server, baseUrl: `http://127.0.0.1:${port}/v1` };
}

// ===== configuration =====

test('provider and tts endpoints are optional and validated together', () => {
  const plain = loadConfig(BASE_ENV);
  assert.equal(plain.provider, undefined);
  assert.equal(plain.tts, undefined);

  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_PROVIDER_BASE_URL: 'https://x.example/v1' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_PROVIDER_API_KEY: 'k' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_TTS_BASE_URL: 'ftp://x.example/v1', OPENMAIC_TTS_API_KEY: 'k' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_TTS_BASE_URL: 'https://u:p@x.example/v1', OPENMAIC_TTS_API_KEY: 'k' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_TTS_BASE_URL: 'https://x.example/v1', OPENMAIC_TTS_API_KEY: 'k', OPENMAIC_TTS_TIMEOUT_SECONDS: '0' }), ConfigError);

  const full = loadConfig({
    ...BASE_ENV,
    OPENMAIC_PROVIDER_BASE_URL: 'https://gen.example/v1/',
    OPENMAIC_PROVIDER_API_KEY: 'k1',
    OPENMAIC_PROVIDER_MODEL: 'm1',
    OPENMAIC_TTS_BASE_URL: 'https://tts.example/v1',
    OPENMAIC_TTS_API_KEY: 'k2',
  });
  assert.deepEqual(full.provider, { baseUrl: 'https://gen.example/v1', apiKey: 'k1', model: 'm1', timeoutMs: 120000 });
  assert.equal(full.tts.model, 'mimo-v2.5-tts');
  assert.equal(full.tts.voice, '苏打');
  assert.equal(full.tts.timeoutMs, 180000);
});

// ===== tts lifecycle =====

test('tts enqueues a job, the worker synthesizes audio, and replay reflects idempotency', async () => {
  const database = new ServiceDatabase(':memory:');
  let responseMode = 'audio';
  const stub = await startStub((request, response) => {
    let raw = '';
    request.on('data', (chunk) => { raw += chunk; });
    request.on('end', () => {
      response.setHeader('content-type', 'application/json');
      if (responseMode === 'audio') {
        response.end(audioPayload(tinyWav()));
      } else if (responseMode === 'broken') {
        response.end('not-json');
      } else {
        response.statusCode = 401;
        response.end(JSON.stringify({ error: { message: 'Invalid token' } }));
      }
    });
  });
  try {
    const { server } = createHarness({
      database,
      routes: [...createTtsRoutes({ database, tts: providerStubConfig(stub.baseUrl, { voice: '苏打' }) }), ...createJobRoutes({ database })],
    });
    await withServer(server, async (base) => {
      const realWorker = createProviderJobWorker({
        database,
        jobs: new JobRepository(database),
        workspaces: new WorkspaceRepository(database),
        tts: providerStubConfig(stub.baseUrl, { voice: '苏打' }),
      });
      const first = await fetch(`${base}/internal/courses/course-1/tts`, {
        method: 'POST',
        headers: { 'x-campusmate-service-assertion': mintAssertion({ scopes: ['tts:write'] }), 'content-type': 'application/json', 'idempotency-key': 'tts-1' },
        body: JSON.stringify({ text: '同学们好' }),
      });
      assert.equal(first.status, 202);
      const firstBody = await first.json();
      assert.equal(firstBody.job.status, 'queued');
      assert.equal(firstBody.voice, '苏打');

      assert.equal(await realWorker.tick(), true);
      const completedJob = new JobRepository(database).get({ userId: 'user-1', courseId: 'course-1', jobId: firstBody.job_id });
      assert.ok(completedJob.artifact_id);
      const completed = await fetch(`${base}/internal/courses/course-1/artifacts/${completedJob.artifact_id}`, {
        headers: { 'x-campusmate-service-assertion': mintAssertion({ scopes: ['job:read'] }) },
      });
      assert.equal(completed.status, 200);
      const artifact = await completed.json();
      assert.equal(artifact.media_type, 'audio/wav');
      assert.equal(Buffer.from(artifact.content_base64, 'base64').subarray(0, 4).toString('ascii'), 'RIFF');

      const replay = await fetch(`${base}/internal/courses/course-1/tts`, {
        method: 'POST',
        headers: { 'x-campusmate-service-assertion': mintAssertion({ scopes: ['tts:write'] }), 'content-type': 'application/json', 'idempotency-key': 'tts-1' },
        body: JSON.stringify({ text: '同学们好' }),
      });
      assert.equal(replay.status, 202);
      assert.equal((await replay.json()).job_id, firstBody.job_id);

      const missing = await fetch(`${base}/internal/courses/course-1/tts`, {
        method: 'POST',
        headers: { 'x-campusmate-service-assertion': mintAssertion({ scopes: ['tts:write'] }), 'content-type': 'application/json' },
        body: JSON.stringify({ text: '同学们好' }),
      });
      assert.equal(missing.status, 400);
    });
  } finally {
    stub.server.close();
  }
});
