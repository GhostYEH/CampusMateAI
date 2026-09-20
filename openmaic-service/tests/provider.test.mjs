import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer as createHttpServer } from 'node:http';

import { ConfigError, loadConfig } from '../src/config.ts';
import { createArchiveRoutes } from '../src/archive/routes.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { createDiscussionRoutes } from '../src/discussion/routes.ts';
import { createGenerationRoutes } from '../src/generation/routes.ts';
import { buildGeneratedStage } from '../src/generation/generator.ts';
import { createJobRoutes } from '../src/jobs/routes.ts';
import { JobRepository } from '../src/jobs/repository.ts';
import { createProviderJobWorker } from '../src/provider/worker.ts';
import { renderStageToMp4 } from '../src/provider/client.ts';
import { createTtsRoutes } from '../src/tts/routes.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const BASE_ENV = { OPENMAIC_INTERNAL_SECRET: 'secret', OPENMAIC_DATABASE_URL: ':memory:' };

function stubConfig(baseUrl, extra = {}) {
  return { baseUrl, apiKey: 'stub-key', model: 'stub-model', timeoutMs: 5000, ...extra };
}

// A realistic model answer: content only — no ids, no timestamps, no wiring.
function rawModelDoc(mode, title) {
  if (mode === 'quiz') {
    return {
      dslVersion: '0.3.0',
      stage: { name: title, description: `关于${title}的自测` },
      scenes: [
        {
          title, type: 'quiz',
          content: { type: 'quiz', questions: [
            {
              type: 'single', question: `关于“${title}”，下面哪个说法更接近本质？`,
              options: [{ label: '趋势与逼近', value: 'a' }, { label: '死记公式', value: 'b' }, { label: '只看函数值', value: 'c' }],
              answer: ['a'], analysis: '极限关心趋势。', points: 1,
            },
          ] },
        },
      ],
    };
  }
  return {
    dslVersion: '0.3.0',
    stage: { name: title, description: `围绕${title}的讲解` },
    scenes: [
      { title, type: 'slide', content: { type: 'slide', slide: { title, sections: [{ heading: '概念解释', bullets: ['导数描述函数值相对于自变量变化的瞬时变化率。'] }] } } },
      { title: `${title}·例子`, type: 'slide', content: { type: 'slide', slide: { title: `${title}·例子`, sections: [{ heading: '具体例子', bullets: ['对 f(x)=x²，在 x=2 处的导数等于 4，表示该点的切线斜率。'] }] } } },
    ],
  };
}

function tinyWav() {
  const buffer = Buffer.alloc(256);
  buffer.write('RIFF', 0, 'ascii');
  buffer.write('WAVE', 8, 'ascii');
  return buffer;
}

const JSON_HEADERS = { 'content-type': 'application/json' };

function assertion(scopes, courseId = 'course-1') {
  return { 'x-campusmate-service-assertion': mintAssertion({ scopes, courseId }) };
}

async function post(base, path, { body, scopes, key }) {
  const headers = { ...assertion(scopes), ...JSON_HEADERS };
  if (key) headers['idempotency-key'] = key;
  const response = await fetch(`${base}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: response.status, body: await response.json() };
}

async function get(base, path, scopes) {
  const response = await fetch(`${base}${path}`, { headers: assertion(scopes) });
  return { status: response.status, body: await response.json() };
}

/** A stand-in upstream whose responses each test controls. */
async function startStub(handler) {
  const server = createHttpServer((request, response) => {
    let raw = '';
    request.on('data', (chunk) => { raw += chunk; });
    request.on('end', () => handler(request, response, raw));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  return { server, baseUrl: `http://127.0.0.1:${port}/v1` };
}

// ===== configuration =====

test('provider and tts endpoints are optional and validated together', () => {
  const plain = loadConfig(BASE_ENV);
  assert.equal(plain.provider, undefined);
  assert.equal(plain.tts, undefined);
  assert.equal(plain.render, undefined);

  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_PROVIDER_BASE_URL: 'https://x.example/v1' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_PROVIDER_API_KEY: 'k' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_TTS_BASE_URL: 'ftp://x.example/v1', OPENMAIC_TTS_API_KEY: 'k' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_TTS_BASE_URL: 'https://u:p@x.example/v1', OPENMAIC_TTS_API_KEY: 'k' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_TTS_BASE_URL: 'https://x.example/v1', OPENMAIC_TTS_API_KEY: 'k', OPENMAIC_TTS_TIMEOUT_SECONDS: '0' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_RENDER_SERVICE_URL: 'http://render-service:9000' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_RENDER_SERVICE_TOKEN: 'render-key' }), ConfigError);

  const full = loadConfig({
    ...BASE_ENV,
    OPENMAIC_PROVIDER_BASE_URL: 'https://gen.example/v1/',
    OPENMAIC_PROVIDER_API_KEY: 'k1',
    OPENMAIC_PROVIDER_MODEL: 'm1',
    OPENMAIC_TTS_BASE_URL: 'https://tts.example/v1',
    OPENMAIC_TTS_API_KEY: 'k2',
    OPENMAIC_RENDER_SERVICE_URL: 'http://render-service:9000',
    OPENMAIC_RENDER_SERVICE_TOKEN: 'render-key',
  });
  assert.deepEqual(full.provider, { baseUrl: 'https://gen.example/v1', apiKey: 'k1', model: 'm1', timeoutMs: 120000 });
  assert.equal(full.tts.model, 'mimo-v2.5-tts');
  assert.equal(full.tts.voice, '苏打');
  assert.equal(full.tts.timeoutMs, 180000);
  assert.deepEqual(full.render, { baseUrl: 'http://render-service:9000', token: 'render-key', timeoutMs: 120000 });
});

test('render client sends only the bounded stage document and accepts mp4 bytes', async () => {
  let seen = null;
  const stub = await startStub((request, response, raw) => {
    seen = { path: request.url, token: request.headers['x-render-service-token'], body: JSON.parse(raw) };
    response.statusCode = 200;
    response.setHeader('content-type', 'video/mp4');
    response.end(Buffer.from('fake-mp4'));
  });
  try {
    const result = await renderStageToMp4(
      { baseUrl: stub.baseUrl, token: 'render-key', timeoutMs: 5000 },
      { stage: { name: '函数极限' }, scenes: [{ title: '定义' }] },
    );
    assert.deepEqual(result, Buffer.from('fake-mp4'));
    assert.equal(seen.path, '/v1/internal/render');
    assert.equal(seen.token, 'render-key');
    assert.deepEqual(seen.body.document.scenes, [{ title: '定义' }]);
  } finally {
    stub.server.close();
  }
});

test('video export is queued, render-service bytes become an owned artifact, and replay is idempotent', async () => {
  const database = new ServiceDatabase(':memory:');
  const workspaces = new WorkspaceRepository(database);
  const workspace = workspaces.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '期末复习' });
  const stage = workspaces.createStage({ userId: 'user-1', courseId: 'course-1', workspaceId: workspace.id, title: '极限', document: buildGeneratedStage('slide', '极限'), dslVersion: '0.3.0' });
  const stub = await startStub((request, response) => {
    assert.equal(request.url, '/v1/internal/render');
    response.statusCode = 200;
    response.setHeader('content-type', 'video/mp4');
    response.end(Buffer.from('real-render-service-output'));
  });
  try {
    const render = { baseUrl: stub.baseUrl, token: 'render-key', timeoutMs: 5000 };
    const jobs = new JobRepository(database);
    const worker = createProviderJobWorker({ database, jobs, workspaces, render });
    const { server } = createHarness({ database, routes: [...createArchiveRoutes({ database, jobs, render }), ...createJobRoutes({ database })] });
    await withServer(server, async (base) => {
      const first = await post(base, `/internal/courses/course-1/workspaces/${workspace.id}/stages/${stage.id}/export/video`, { body: {}, scopes: ['archive:read', 'job:write'], key: 'video-1' });
      assert.equal(first.status, 202);
      assert.equal(first.body.format, 'mp4');
      const replay = await post(base, `/internal/courses/course-1/workspaces/${workspace.id}/stages/${stage.id}/export/video`, { body: {}, scopes: ['archive:read', 'job:write'], key: 'video-1' });
      assert.equal(replay.body.job_id, first.body.job_id);
      assert.equal(await worker.tick(), true);
      const job = await get(base, `/internal/courses/course-1/jobs/${first.body.job_id}`, ['job:read']);
      assert.equal(job.body.status, 'completed');
      const artifact = await get(base, `/internal/courses/course-1/artifacts/${job.body.artifact_id}`, ['job:read']);
      assert.equal(artifact.body.media_type, 'video/mp4');
      assert.equal(Buffer.from(artifact.body.content_base64, 'base64').toString(), 'real-render-service-output');
    });
  } finally {
    stub.server.close();
  }
});

// ===== tts =====

test('tts: enqueue, worker synthesis, artifact download, replay, and honest failure', async () => {
  const database = new ServiceDatabase(':memory:');
  let mode = 'audio';
  const stub = await startStub((request, response) => {
    response.setHeader('content-type', 'application/json');
    if (mode === 'audio') response.end(JSON.stringify({ choices: [{ message: { audio: { data: tinyWav().toString('base64') } } }] }));
    else if (mode === 'broken') response.end('definitely not json');
    else { response.statusCode = 503; response.end(JSON.stringify({ error: { message: 'upstream down' } })); }
  });
  try {
    const jobs = new JobRepository(database);
    const worker = createProviderJobWorker({ database, jobs, workspaces: new WorkspaceRepository(database), tts: stubConfig(stub.baseUrl, { voice: '苏打' }) });
    const { server } = createHarness({ database, routes: [...createTtsRoutes({ database, tts: stubConfig(stub.baseUrl, { voice: '苏打' }) }), ...createJobRoutes({ database })] });
    await withServer(server, async (base) => {
      const first = await post(base, '/internal/courses/course-1/tts', { body: { text: '同学们好，我们开始上课。' }, scopes: ['tts:write'], key: 'tts-1' });
      assert.equal(first.status, 202);
      assert.equal(first.body.job.status, 'queued');
      assert.equal(first.body.voice, '苏打');
      const jobId = first.body.job_id;

      const replay = await post(base, '/internal/courses/course-1/tts', { body: { text: '同学们好，我们开始上课。' }, scopes: ['tts:write'], key: 'tts-1' });
      assert.equal(replay.status, 202);
      assert.equal(replay.body.job_id, jobId);

      const missing = await post(base, '/internal/courses/course-1/tts', { body: { text: '同学们好' }, scopes: ['tts:write'] });
      assert.equal(missing.status, 400);

      assert.equal(await worker.tick(), true);
      let job = await get(base, `/internal/courses/course-1/jobs/${jobId}`, ['job:read']);
      assert.equal(job.body.status, 'completed');
      assert.ok(job.body.artifact_id);

      const artifact = await get(base, `/internal/courses/course-1/artifacts/${job.body.artifact_id}`, ['job:read']);
      const wav = Buffer.from(artifact.body.content_base64, 'base64');
      assert.equal(wav.subarray(0, 4).toString('ascii'), 'RIFF');
      assert.equal(artifact.body.media_type, 'audio/wav');

      mode = 'broken';
      const second = await post(base, '/internal/courses/course-1/tts', { body: { text: '再来一段' }, scopes: ['tts:write'], key: 'tts-2' });
      assert.equal(await worker.tick(), true);
      job = await get(base, `/internal/courses/course-1/jobs/${second.body.job_id}`, ['job:read']);
      assert.equal(job.body.status, 'failed');
      assert.equal(job.body.error_code, 'provider_invalid_response');

      const retried = await post(base, `/internal/courses/course-1/jobs/${second.body.job_id}/retry`, { body: {}, scopes: ['job:write'] });
      assert.equal(retried.body.status, 'queued');
      mode = 'audio';
      assert.equal(await worker.tick(), true);
      job = await get(base, `/internal/courses/course-1/jobs/${second.body.job_id}`, ['job:read']);
      assert.equal(job.body.status, 'completed');
    });
  } finally {
    stub.server.close();
  }
});

test('tts without a configured provider still answers 503 and never fabricates audio', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: createTtsRoutes({ database }) });
  await withServer(server, async (base) => {
    const result = await post(base, '/internal/courses/course-1/tts', { body: { text: '你好' }, scopes: ['tts:write'], key: 'tts-1' });
    assert.equal(result.status, 503);
    assert.equal(result.body.error, 'provider_unavailable');
    assert.equal(result.body.audio_base64, undefined);
  });
});

// ===== generation =====

test('generation with a provider: enqueue, worker produces a DSL-valid stage, honest failure then retry', async () => {
  const database = new ServiceDatabase(':memory:');
  const workspaces = new WorkspaceRepository(database);
  const workspace = workspaces.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '测试工作台' });
  let mode = 'doc';
  const stub = await startStub((request, response) => {
    response.setHeader('content-type', 'application/json');
    if (mode === 'doc') response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(rawModelDoc('quiz', '函数的极限')) } }] }));
    else if (mode === 'fenced') response.end(JSON.stringify({ choices: [{ message: { content: '```json\n' + JSON.stringify(rawModelDoc('slide', '导数')) + '\n```' } }] }));
    else response.end(JSON.stringify({ choices: [{ message: { content: 'no json here at all' } }] }));
  });
  try {
    const jobs = new JobRepository(database);
    const worker = createProviderJobWorker({ database, jobs, workspaces, provider: stubConfig(stub.baseUrl) });
    const { server } = createHarness({ database, routes: [...createGenerationRoutes({ database, provider: stubConfig(stub.baseUrl) }), ...createJobRoutes({ database })] });
    await withServer(server, async (base) => {
      const first = await post(base, `/internal/courses/course-1/workspaces/${workspace.id}/generate`, { body: { mode: 'quiz', prompt: '函数的极限' }, scopes: ['generation:write', 'workspace:write', 'job:write'], key: 'gen-1' });
      assert.equal(first.status, 201);
      assert.equal(first.body.source, 'provider');
      assert.equal(first.body.job.status, 'queued');
      assert.equal(first.body.stage_id, undefined);
      const jobId = first.body.job_id;

      assert.equal(await worker.tick(), true);
      const job = await get(base, `/internal/courses/course-1/jobs/${jobId}`, ['job:read']);
      assert.equal(job.body.status, 'completed');
      const stageCount = database.raw.prepare('SELECT count(*) AS n FROM stages WHERE workspace_id = ?').get(workspace.id);
      assert.equal(stageCount.n, 1);
      const artifact = await get(base, `/internal/courses/course-1/artifacts/${job.body.artifact_id}`, ['job:read']);
      const document = JSON.parse(Buffer.from(artifact.body.content_base64, 'base64').toString('utf8'));
      assert.equal(document.scenes[0].type, 'quiz');
      // The stub answered like a real model (no identities); the service owns ids.
      assert.ok(document.stage.id.startsWith('stage_'));
      assert.ok(document.scenes[0].id.startsWith('scene_'));
      assert.equal(document.scenes[0].stageId, document.stage.id);
      assert.ok(document.scenes[0].content.questions[0].id.startsWith('question_'));
      assert.equal(typeof document.stage.createdAt, 'number');

      mode = 'garbage';
      const second = await post(base, `/internal/courses/course-1/workspaces/${workspace.id}/generate`, { body: { mode: 'slide', prompt: '导数' }, scopes: ['generation:write', 'workspace:write', 'job:write'], key: 'gen-2' });
      assert.equal(await worker.tick(), true);
      const failed = await get(base, `/internal/courses/course-1/jobs/${second.body.job_id}`, ['job:read']);
      assert.equal(failed.body.status, 'failed');
      assert.equal(failed.body.error_code, 'provider_invalid_response');

      mode = 'fenced';
      await post(base, `/internal/courses/course-1/jobs/${second.body.job_id}/retry`, { body: {}, scopes: ['job:write'] });
      assert.equal(await worker.tick(), true);
      const recovered = await get(base, `/internal/courses/course-1/jobs/${second.body.job_id}`, ['job:read']);
      assert.equal(recovered.body.status, 'completed');
    });
  } finally {
    stub.server.close();
  }
});

test('generation without a provider keeps the synchronous local-template contract', async () => {
  const database = new ServiceDatabase(':memory:');
  const workspaces = new WorkspaceRepository(database);
  const workspace = workspaces.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '测试工作台' });
  const { server } = createHarness({ database, routes: createGenerationRoutes({ database }) });
  await withServer(server, async (base) => {
    const result = await post(base, `/internal/courses/course-1/workspaces/${workspace.id}/generate`, { body: { mode: 'slide', prompt: '函数的极限' }, scopes: ['generation:write', 'workspace:write', 'job:write'], key: 'gen-1' });
    assert.equal(result.status, 201);
    assert.equal(result.body.source, 'local-template');
    assert.ok(result.body.stage_id);
  });
});

// ===== discussion =====

test('discussion: enqueue, worker roundtable artifact, and degraded contract without a provider', async () => {
  const database = new ServiceDatabase(':memory:');
  const roundtable = JSON.stringify({ messages: [
    { agent: '主讲人', content: '极限描述的是函数的趋势。' },
    { agent: '追问者', content: '那左右极限不相等时呢？' },
    { agent: '总结者', content: '左右极限一致才有极限。' },
  ] });
  const stub = await startStub((request, response) => {
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify({ choices: [{ message: { content: roundtable } }] }));
  });
  try {
    const jobs = new JobRepository(database);
    const worker = createProviderJobWorker({ database, jobs, workspaces: new WorkspaceRepository(database), provider: stubConfig(stub.baseUrl) });
    const { server } = createHarness({ database, routes: [...createDiscussionRoutes({ database, provider: stubConfig(stub.baseUrl) }), ...createJobRoutes({ database })] });
    await withServer(server, async (base) => {
      const result = await post(base, '/internal/courses/course-1/discussion', { body: { prompt: '讨论函数极限的定义' }, scopes: ['multi-agent:write'], key: 'd-1' });
      assert.equal(result.status, 202);
      assert.equal(await worker.tick(), true);
      const job = await get(base, `/internal/courses/course-1/jobs/${result.body.job_id}`, ['job:read']);
      assert.equal(job.body.status, 'completed');
      const artifact = await get(base, `/internal/courses/course-1/artifacts/${job.body.artifact_id}`, ['job:read']);
      const discussion = JSON.parse(Buffer.from(artifact.body.content_base64, 'base64').toString('utf8'));
      assert.equal(discussion.messages.length, 3);
      assert.equal(discussion.messages[0].agent, '主讲人');
    });
  } finally {
    stub.server.close();
  }

  const degraded = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database: degraded, routes: createDiscussionRoutes({ database: degraded }) });
  await withServer(server, async (base) => {
    const result = await post(base, '/internal/courses/course-1/discussion', { body: { prompt: '讨论函数极限的定义' }, scopes: ['multi-agent:write'], key: 'd-2' });
    assert.equal(result.status, 503);
    assert.equal(result.body.error, 'provider_unavailable');
  });
});
