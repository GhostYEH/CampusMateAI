/**
 * 场景讲解音频的合约测试。
 *
 * 这组测试盯住四件事，它们都是"讲课有声音"这条链路真正会坏掉的地方：
 *
 * 1. 讲稿由**服务端从场景正文派生**，不是客户端传什么就读什么；
 * 2. 音频与场景**一一对应**——scene A 的音频绝不会被当成 scene B 的；
 * 3. 重复点击**不重复计费**（复用已完成任务 / 复用在飞任务 / 幂等重放）；
 * 4. 讲稿为空、provider 不可用、场景不存在时都**如实回报**，不合成假音频。
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { JobRepository } from '../src/jobs/repository.ts';
import { createJobRoutes } from '../src/jobs/routes.ts';
import { createProviderJobWorker } from '../src/provider/worker.ts';
import { buildSceneNarration, MAX_NARRATION_CHARS } from '../src/tts/narration.ts';
import { createSceneNarrationRoutes } from '../src/tts/scene-narration-routes.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const TTS = { baseUrl: 'http://127.0.0.1:1/v1', apiKey: 'k', model: 'mimo-v2.5-tts', voice: '茉莉', timeoutMs: 1000 };

/**
 * 每个请求都铸一枚**新的**断言：断言带 jti 且一次性消费，复用同一枚会被
 * 当成重放拒掉（403），那与"业务被拒"混在一起就分不清了。
 */
function headers(scopes, courseId = 'course-1', key) {
  const base = { 'x-campusmate-service-assertion': mintAssertion({ scopes, courseId }), 'content-type': 'application/json' };
  if (key) base['idempotency-key'] = key;
  return base;
}

async function call(base, method, path, { body, scopes, courseId, key } = {}) {
  const response = await fetch(`${base}${path}`, {
    method, headers: headers(scopes, courseId, key),
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return { status: response.status, body: await response.json() };
}

/**
 * 建一个工作台 + 舞台，返回 { workspaceId, stageId }。
 *
 * 文档要过 DSL 校验：stage 必须有 id/name/createdAt/updatedAt，场景的 stageId
 * 必须与所属 stage 一致。补齐这些才能拿到 201，否则测的是校验器而不是讲解链路。
 */
async function seedStage(base, scenes) {
  const workspace = await call(base, 'POST', '/internal/courses/course-1/workspaces', {
    body: { name: '课堂' }, scopes: ['workspace:write'], key: 'ws-1',
  });
  assert.equal(workspace.status, 201, `workspace seed failed: ${JSON.stringify(workspace.body)}`);
  const workspaceId = workspace.body.id;

  const stage = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspaceId}/stages`, {
    body: {
      title: '讲解',
      document: {
        dslVersion: '0.3.0',
        stage: { id: 'stage-1', name: '讲解', createdAt: 1, updatedAt: 1 },
        scenes: scenes.map((scene) => ({ ...scene, stageId: 'stage-1' })),
      },
    },
    scopes: ['workspace:write'], key: 'st-1',
  });
  assert.equal(stage.status, 201, `stage seed failed: ${JSON.stringify(stage.body)}`);
  return { workspaceId, stageId: stage.body.id };
}

function narrationUrl(workspaceId, stageId, sceneId) {
  return `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/scenes/${sceneId}/narration`;
}

function buildRoutes(database, tts = TTS) {
  const workspaces = new WorkspaceRepository(database);
  return [
    ...createWorkspaceRoutes({ database }),
    ...createJobRoutes({ database }),
    ...createSceneNarrationRoutes({ database, workspaces, tts }),
  ];
}

/** provider 未配置（`tts` 为 undefined）的路由集，用于验证如实降级。 */
function buildRoutesWithoutProvider(database) {
  const workspaces = new WorkspaceRepository(database);
  return [
    ...createWorkspaceRoutes({ database }),
    ...createJobRoutes({ database }),
    ...createSceneNarrationRoutes({ database, workspaces, tts: undefined, available: false }),
  ];
}

const TWO_SCENES = [
  { id: 'scene-a', title: '牛顿第一定律', order: 0, type: 'slide', content: { type: 'slide', slide: { title: '牛顿第一定律', bullets: ['物体保持静止或匀速直线运动'] }, canvas: { title: '牛顿第一定律', body: '物体保持静止或匀速直线运动' } } },
  { id: 'scene-b', title: '动量守恒', order: 1, type: 'slide', content: { type: 'slide', slide: { title: '动量守恒', bullets: ['系统不受外力时总动量不变'] }, canvas: { title: '动量守恒', body: '系统不受外力时总动量不变' } } },
];

// ===== 讲稿派生 =====

test('narration is derived from the scene body, per scene type', () => {
  const slide = buildSceneNarration(TWO_SCENES[0]);
  assert.match(slide.text, /牛顿第一定律/);
  assert.match(slide.text, /保持静止或匀速直线运动/);
  assert.equal(slide.truncated, false);

  const quiz = buildSceneNarration({
    type: 'quiz', title: '自测',
    content: { type: 'quiz', questions: [{ id: 'q1', type: 'single', question: '极限的定义是什么？', analysis: '关心趋势。', answer: ['a'] }] },
  });
  assert.match(quiz.text, /极限的定义/);
  assert.match(quiz.text, /关心趋势/);
  // 答案绝不能被读出来——那会破坏自测的教学用途。
  assert.doesNotMatch(quiz.text, /a/);
});

test('slide narration includes detailed text stored in rendered canvas elements', () => {
  const slide = buildSceneNarration({
    type: 'slide',
    title: '生成的课程页',
    content: {
      type: 'slide',
      slide: { title: '生成的课程页', bullets: [] },
      canvas: {
        elements: [
          { type: 'shape', content: '装饰图形' },
          { type: 'text', content: '<p>这是生成服务写入的详细正文。</p>' },
        ],
      },
    },
  });
  assert.match(slide.text, /详细正文/);
  assert.doesNotMatch(slide.text, /<p>|装饰图形/);
});

test('narration never reads internal widget fields or raw html', () => {
  const interactive = buildSceneNarration({
    type: 'interactive', title: '自由落体实验',
    content: { type: 'interactive', html: '<main><script>alert(1)</script></main>', widgetType: 'simulation', widgetConfig: { type: 'simulation', prompt: '调整重力加速度' } },
  });
  assert.match(interactive.text, /自由落体实验/);
  assert.match(interactive.text, /调整重力加速度/);
  assert.doesNotMatch(interactive.text, /script|alert|widgetType/);
});

test('an empty scene yields an empty script rather than a fabricated one', () => {
  assert.equal(buildSceneNarration({ type: 'slide', title: '', content: { type: 'slide', canvas: {} } }).text, '');
  // 有标题但正文为空时，至少把标题读出来。
  assert.match(buildSceneNarration({ type: 'slide', title: '标题页', content: { type: 'slide', canvas: {} } }).text, /标题页/);
  // quiz 只有题目没有解析时，仍应读出题干。
  assert.match(buildSceneNarration({ type: 'quiz', title: '自测', content: { type: 'quiz', questions: [{ id: 'q', type: 'single', question: '什么是惯性？' }] } }).text, /什么是惯性/);
});

test('an over-long script is truncated and marked, not refused', () => {
  // 用结构化 sections（每节至多 6 条、每条约 40 字），把讲稿推到上限之上。
  const long = buildSceneNarration({
    type: 'slide', title: '长页',
    content: {
      type: 'slide',
      slide: {
        title: '长页',
        bullets: Array.from({ length: 8 }, (_, i) => `要点${i}：${'这'.repeat(40)}`),
        sections: Array.from({ length: 3 }, (_, s) => ({
          heading: `第${s}部分`,
          bullets: Array.from({ length: 6 }, (_, i) => `小节${s}-${i}：${'那'.repeat(40)}`),
        })),
      },
    },
  });
  assert.equal(long.truncated, true);
  assert.equal(long.text.length, MAX_NARRATION_CHARS);
  assert.ok(long.originalLength > MAX_NARRATION_CHARS);
});

// ===== 场景归属：A 页不会拿到 B 页的音频 =====

test('two scenes produce two distinct jobs, each bound to its own scene', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);

    const a = await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-a'), { scopes: ['tts:write'], key: 'n-a' });
    const b = await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-b'), { scopes: ['tts:write'], key: 'n-b' });

    assert.equal(a.status, 201);
    assert.equal(b.status, 201);
    assert.equal(a.body.scene_id, 'scene-a');
    assert.equal(b.body.scene_id, 'scene-b');
    assert.equal(a.body.job.scene_id, 'scene-a');
    assert.equal(b.body.job.scene_id, 'scene-b');
    // 两个场景必须是**两个不同的任务**，否则音频会串页。
    assert.notEqual(a.body.job.id, b.body.job.id);

    // 每个任务的讲稿只含自己那一页的内容。
    const jobs = new JobRepository(database);
    const inputA = JSON.parse(jobs.get({ userId: 'user-1', courseId: 'course-1', jobId: a.body.job.id }).input_json);
    const inputB = JSON.parse(jobs.get({ userId: 'user-1', courseId: 'course-1', jobId: b.body.job.id }).input_json);
    assert.match(inputA.text, /牛顿第一定律/);
    assert.doesNotMatch(inputA.text, /动量守恒/);
    assert.match(inputB.text, /动量守恒/);
    assert.doesNotMatch(inputB.text, /牛顿第一定律/);
    // 用的是配置里的 mimo 模型与音色，客户端无从覆写。
    assert.equal(jobs.get({ userId: 'user-1', courseId: 'course-1', jobId: a.body.job.id }).mode, 'mimo-v2.5-tts');
    assert.equal(inputA.voice, '茉莉');
  });
});

test('reading scene A narration never returns scene B job', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-b'), { scopes: ['tts:write'], key: 'n-b' });

    // 把 B 标成完成，再读 A：A 必须是"还没有"，绝不能被 B 的产物顶上。
    const jobs = new JobRepository(database);
    const active = jobs.findActiveSceneNarration({ userId: 'user-1', courseId: 'course-1', sceneId: 'scene-b' });
    jobs.complete({
      userId: 'user-1', courseId: 'course-1', jobId: active.id,
      artifact: { filename: 'b.wav', mediaType: 'audio/wav', payload: Buffer.from('RIFFWAVE') },
    });

    const readA = await call(base, 'GET', narrationUrl(workspaceId, stageId, 'scene-a'), { scopes: ['tts:read'] });
    assert.equal(readA.status, 200);
    assert.equal(readA.body.scene_id, 'scene-a');
    assert.equal(readA.body.job, null);

    const readB = await call(base, 'GET', narrationUrl(workspaceId, stageId, 'scene-b'), { scopes: ['tts:read'] });
    assert.equal(readB.body.job.scene_id, 'scene-b');
    assert.ok(readB.body.job.artifact_id);
  });
});

// ===== 重复点击不重复计费 =====

test('repeated clicks reuse the finished narration instead of paying again', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    const url = narrationUrl(workspaceId, stageId, 'scene-a');

    const first = await call(base, 'POST', url, { scopes: ['tts:write'], key: 'k-1' });
    const jobs = new JobRepository(database);
    jobs.complete({
      userId: 'user-1', courseId: 'course-1', jobId: first.body.job.id,
      artifact: { filename: 'a.wav', mediaType: 'audio/wav', payload: Buffer.from('RIFFWAVE') },
    });

    // 换一个幂等键、重新点：应当复用同一个成品，而不是新建任务。
    const second = await call(base, 'POST', url, { scopes: ['tts:write'], key: 'k-2' });
    assert.equal(second.status, 200);
    assert.equal(second.body.reuse, true);
    assert.equal(second.body.job.id, first.body.job.id);
  });
});

test('a queued narration is reused rather than duplicated', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    const url = narrationUrl(workspaceId, stageId, 'scene-a');
    const first = await call(base, 'POST', url, { scopes: ['tts:write'], key: 'k-1' });
    const again = await call(base, 'POST', url, { scopes: ['tts:write'], key: 'k-2' });
    assert.equal(again.body.reuse, true);
    assert.equal(again.body.job.id, first.body.job.id);
  });
});

test('the same idempotency key replays instead of creating a second job', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    const url = narrationUrl(workspaceId, stageId, 'scene-a');
    const first = await call(base, 'POST', url, { scopes: ['tts:write'], key: 'same' });
    const replay = await call(base, 'POST', url, { scopes: ['tts:write'], key: 'same' });
    assert.equal(replay.body.job.id, first.body.job.id);
  });
});

// ===== 如实降级 =====

test('a scene whose script derives empty reports so and creates no job', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    // DSL 要求场景必须有非空标题，所以一条**落库**的场景至少能读出标题。这里直接
    // 用一行只有标点的场景来触发"派生讲稿为空"这条分支：标点会被清洗掉。
    const { workspaceId, stageId } = await seedStage(base, [
      { id: 'scene-empty', title: '。', order: 0, type: 'slide', content: { type: 'slide', canvas: {} } },
    ]);
    const result = await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-empty'), { scopes: ['tts:write'], key: 'k-empty' });
    // 标点被清洗后标题不再是一句话，派生讲稿为空 → 如实回报且不建任务。
    assert.equal(result.status, 200);
    assert.equal(result.body.has_script, false);
    assert.equal(result.body.job, null);
    const jobs = new JobRepository(database);
    assert.equal(jobs.findActiveSceneNarration({ userId: 'user-1', courseId: 'course-1', sceneId: 'scene-empty' }), null);
  });
});

test('narration reports provider degradation honestly and creates no artifact', async () => {
  const database = new ServiceDatabase(':memory:');
  // 不传 tts：能力未配置，必须 503 而不是产出一段空音频。
  const { server } = createHarness({ database, routes: buildRoutesWithoutProvider(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    const result = await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-a'), { scopes: ['tts:write'], key: 'k-1' });
    assert.equal(result.status, 503);
    assert.equal(result.body.error, 'provider_unavailable');
    assert.equal(result.body.artifact_id, undefined);
  });
});

test('an unknown scene is a plain not-found, not an empty narration', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    const result = await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-nope'), { scopes: ['tts:write'], key: 'k-1' });
    assert.equal(result.status, 404);
  });
});

test('narration requires the tts scope and the matching course', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: buildRoutes(database) });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    const url = narrationUrl(workspaceId, stageId, 'scene-a');
    const noScope = await call(base, 'POST', url, { scopes: ['workspace:read'], key: 'k-1' });
    assert.equal(noScope.status, 403);

    // 用别的课程的断言访问这门课的舞台：必须被拒。
    const otherCourse = await call(base, 'GET', url, { scopes: ['tts:read'], courseId: 'course-2' });
    assert.equal(otherCourse.status, 403);
  });
});

// ===== 失败不影响 PPT 本身 =====

test('a failing tts provider marks the job failed and leaves the stage readable', async () => {
  const database = new ServiceDatabase(':memory:');
  const routes = buildRoutes(database);
  const jobs = new JobRepository(database);
  const workspaces = new WorkspaceRepository(database);
  // 指向一个必然连不上的上游：任务应当变成 failed，而不是抛出去影响别的东西。
  const worker = createProviderJobWorker({
    database, jobs, workspaces,
    tts: { baseUrl: 'http://127.0.0.1:9/v1', apiKey: 'k', model: 'mimo-v2.5-tts', voice: '茉莉', timeoutMs: 500 },
  });
  const { server } = createHarness({ database, routes });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
    const payload = JSON.parse(workspaces.getStage({ userId: 'user-1', courseId: 'course-1', workspaceId, stageId }).document);

    const started = await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-a'), { scopes: ['tts:write'], key: 'k-1' });
    await worker.tick();

    const job = jobs.get({ userId: 'user-1', courseId: 'course-1', jobId: started.body.job.id });
    assert.equal(job.status, 'failed');
    assert.ok(job.error_code);
    assert.equal(job.artifact_id, null);

    // 任务失败之后，舞台文档必须原样可读——PPT 不受音频失败影响。
    const after = JSON.parse(workspaces.getStage({ userId: 'user-1', courseId: 'course-1', workspaceId, stageId }).document);
    assert.deepEqual(after, payload);

    const read = await call(base, 'GET', narrationUrl(workspaceId, stageId, 'scene-a'), { scopes: ['tts:read'] });
    assert.equal(read.status, 200);
    assert.equal(read.body.job, null);
  });
});

test('a successful narration lands as a wav artifact named after its scene', async () => {
  const database = new ServiceDatabase(':memory:');
  const routes = buildRoutes(database);
  const jobs = new JobRepository(database);
  const workspaces = new WorkspaceRepository(database);

  // 一个假上游，回一段最小合法 WAV（与 provider.test.mjs 同款）。
  const { createServer: createHttpServer } = await import('node:http');
  const upstream = createHttpServer((request, response) => {
    let raw = '';
    request.on('data', (chunk) => { raw += chunk; });
    request.on('end', () => {
      const buffer = Buffer.alloc(256);
      buffer.write('RIFF', 0, 'ascii');
      buffer.write('WAVE', 8, 'ascii');
      response.writeHead(200, { 'content-type': 'application/json' });
      response.end(JSON.stringify({ choices: [{ message: { audio: { data: buffer.toString('base64') } } }] }));
    });
  });
  await new Promise((resolve) => upstream.listen(0, '127.0.0.1', resolve));
  const upstreamBase = `http://127.0.0.1:${upstream.address().port}/v1`;

  try {
    const worker = createProviderJobWorker({
      database, jobs, workspaces,
      tts: { baseUrl: upstreamBase, apiKey: 'k', model: 'mimo-v2.5-tts', voice: '茉莉', timeoutMs: 5000 },
    });
    const { server } = createHarness({ database, routes });
    await withServer(server, async (base) => {
      const { workspaceId, stageId } = await seedStage(base, TWO_SCENES);
      const started = await call(base, 'POST', narrationUrl(workspaceId, stageId, 'scene-a'), { scopes: ['tts:write'], key: 'k-1' });
      await worker.tick();

      const job = jobs.get({ userId: 'user-1', courseId: 'course-1', jobId: started.body.job.id });
      assert.equal(job.status, 'completed');
      // 任务上仍然带着场景归属：刷新页面后靠它把音频挂回正确的页。
      assert.equal(job.scene_id, 'scene-a');

      const artifact = await call(base, 'GET', `/internal/courses/course-1/artifacts/${job.artifact_id}`, { scopes: ['job:read'] });
      assert.equal(artifact.body.media_type, 'audio/wav');
      assert.match(artifact.body.filename, /牛顿第一定律/);
      assert.ok(Buffer.from(artifact.body.content_base64, 'base64').length > 0);

      // 生成完成后再读一次：客户端不需要记住 job 或 artifact id。
      const read = await call(base, 'GET', narrationUrl(workspaceId, stageId, 'scene-a'), { scopes: ['tts:read'] });
      assert.equal(read.body.job.scene_id, 'scene-a');
      assert.equal(read.body.job.artifact_id, job.artifact_id);
      assert.equal(read.body.stale, false);
    });
  } finally {
    upstream.close();
  }
});
