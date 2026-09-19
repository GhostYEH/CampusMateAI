/**
 * Playback plan tests.
 *
 * The player's job is to be *truthful*: it must render what it can, and say
 * plainly what it cannot. These tests therefore care most about degradation
 * (`unsupported` with a reason instead of a blank native frame), about the
 * sandbox never gaining `allow-same-origin`, and about actions that are dropped
 * being reported rather than silently disappearing.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { createEditorRoutes } from '../src/editor/routes.ts';
import {
  SCENE_SANDBOX,
  buildPlaybackPlan,
} from '../src/player/playback.ts';
import { createPlayerRoutes } from '../src/player/routes.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';
import { mintAssertion, withServer, createHarness } from './helpers.mjs';

const SCOPES = ['workspace:read', 'workspace:write', 'stage:read', 'stage:write'];

function harness({ externalCdnAvailable = false } = {}) {
  const database = new ServiceDatabase(':memory:');
  const routes = [
    ...createWorkspaceRoutes({ database }),
    ...createEditorRoutes({ database }),
    ...createPlayerRoutes({ database, capabilities: { externalCdnAvailable } }),
  ];
  return { database, ...createHarness({ database, routes }) };
}

function headers({ sub = 'user-1', courseId = 'course-1', scopes = SCOPES, extra = {} } = {}) {
  return {
    'x-campusmate-service-assertion': mintAssertion({ sub, courseId, scopes }),
    'content-type': 'application/json',
    ...extra,
  };
}

async function call(base, method, path, { body, headers: requestHeaders } = {}) {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: requestHeaders ?? headers(),
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : null };
}

let keyCounter = 0;
const nextKey = () => `pk-${(keyCounter += 1)}`;

async function seedStage(base, commands) {
  const workspace = await call(base, 'POST', '/internal/courses/course-1/workspaces', {
    body: { name: '播放测试' },
    headers: headers({ extra: { 'idempotency-key': nextKey() } }),
  });
  const workspaceId = workspace.body.id;
  const stage = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspaceId}/stages`, {
    body: { title: '第一课' },
    headers: headers({ extra: { 'idempotency-key': nextKey() } }),
  });
  const stageId = stage.body.id;
  if (commands) {
    const applied = await call(
      base,
      'POST',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/commands`,
      {
        body: { commands },
        headers: { ...headers(), 'if-match': String(stage.body.revision), 'idempotency-key': nextKey() },
      },
    );
    assert.equal(applied.status, 200, JSON.stringify(applied.body));
  }
  return { workspaceId, stageId };
}

const playbackPath = (workspaceId, stageId) =>
  `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/playback`;

// ===== 纯计划层 =====

function aggregate(scenes) {
  return {
    dslVersion: '0.3.0',
    stage: { id: 'stg_1', name: '第一课', createdAt: 1, updatedAt: 1 },
    scenes,
  };
}

const scene = (overrides) => ({
  id: 'scn_1',
  stageId: 'stg_1',
  title: '场景',
  order: 0,
  type: 'slide',
  content: { type: 'slide', canvas: {} },
  ...overrides,
});

test('the only sandbox the player applies is allow-scripts', () => {
  assert.equal(SCENE_SANDBOX, 'allow-scripts');
  assert.doesNotMatch(SCENE_SANDBOX, /allow-same-origin/);
});

test('an unknown scene type degrades explicitly instead of rendering blank', () => {
  const plan = buildPlaybackPlan(
    aggregate([scene({ type: 'whiteboard', content: { type: 'whiteboard' } })]),
    { workspaceId: 'ws_1', revision: 1, dslVersion: '0.3.0' },
    { externalCdnAvailable: true },
  );
  assert.equal(plan.scenes[0].render.kind, 'unsupported');
  assert.equal(plan.scenes[0].render.reason, 'scene_type_unsupported');
  assert.equal(plan.scenes[0].type, 'unknown');
  assert.deepEqual(plan.degraded, [{ scene_id: 'scn_1', reason: 'scene_type_unsupported' }]);
});

test('visualization3d degrades without a CDN and sandboxes with one', () => {
  const document = aggregate([
    scene({
      type: 'interactive',
      content: { type: 'interactive', html: '<p>3d</p>', widgetType: 'visualization3d' },
    }),
  ]);
  const without = buildPlaybackPlan(document, { workspaceId: 'ws_1', revision: 1, dslVersion: '0.3.0' }, { externalCdnAvailable: false });
  assert.equal(without.scenes[0].render.kind, 'unsupported');
  assert.equal(without.scenes[0].render.reason, 'widget_requires_external_cdn');

  const withCdn = buildPlaybackPlan(document, { workspaceId: 'ws_1', revision: 1, dslVersion: '0.3.0' }, { externalCdnAvailable: true });
  assert.equal(withCdn.scenes[0].render.kind, 'sandbox-html');
  assert.equal(withCdn.scenes[0].render.widget_type, 'visualization3d');
});

test('interactive url content is sandboxed as a url, not as html', () => {
  const plan = buildPlaybackPlan(
    aggregate([scene({ type: 'interactive', content: { type: 'interactive', url: 'https://example.com/x' } })]),
    { workspaceId: 'ws_1', revision: 1, dslVersion: '0.3.0' },
    { externalCdnAvailable: true },
  );
  assert.equal(plan.scenes[0].render.kind, 'sandbox-url');
  assert.equal(plan.scenes[0].render.sandbox, SCENE_SANDBOX);
});

test('slide-only actions are dropped on other scene types and reported', () => {
  const actions = [
    { id: 'a1', type: 'spotlight' },
    { id: 'a2', type: 'speech', text: '讲解' },
  ];
  const plan = buildPlaybackPlan(
    aggregate([
      scene({ id: 'scn_slide', order: 0, actions }),
      scene({ id: 'scn_quiz', order: 1, type: 'quiz', content: { type: 'quiz', questions: [] }, actions }),
    ]),
    { workspaceId: 'ws_1', revision: 1, dslVersion: '0.3.0' },
    { externalCdnAvailable: true },
  );

  assert.deepEqual(
    plan.scenes[0].steps.map((step) => [step.action_id, step.mode]),
    [['a1', 'fire_and_forget'], ['a2', 'sync']],
  );
  assert.deepEqual(plan.scenes[1].steps.map((step) => step.action_id), ['a2']);
  assert.deepEqual(plan.scenes[1].dropped_actions, [
    { action_id: 'a1', type: 'spotlight', reason: 'action_requires_slide_scene' },
  ]);
});

test('a resume position that is not in this stage is an explicit error', () => {
  assert.throws(
    () => buildPlaybackPlan(
      aggregate([scene({})]),
      { workspaceId: 'ws_1', revision: 1, dslVersion: '0.3.0', startSceneId: 'scn_missing' },
      { externalCdnAvailable: true },
    ),
    (error) => error.code === 'scene_not_found',
  );
});

// ===== HTTP =====

test('the playback plan lists scenes in order with their render decisions', async () => {
  const { server } = harness({ externalCdnAvailable: true });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, [
      { type: 'scene.create', sceneType: 'slide', title: '开场' },
      { type: 'scene.create', sceneType: 'quiz', title: '小测' },
      {
        type: 'scene.create',
        sceneType: 'interactive',
        title: '模拟',
        content: { type: 'interactive', html: '<p>sim</p>', widgetType: 'simulation' },
      },
    ]);

    const plan = await call(base, 'GET', playbackPath(workspaceId, stageId));
    assert.equal(plan.status, 200);
    assert.equal(plan.body.scenes.length, 3);
    assert.deepEqual(plan.body.scenes.map((item) => item.render.kind), ['native', 'native', 'sandbox-html']);
    assert.equal(plan.body.scenes[2].render.sandbox, 'allow-scripts');
    assert.equal(JSON.stringify(plan.body).includes('allow-same-origin'), false);
    assert.equal(plan.body.start_index, 0);
    assert.deepEqual(plan.body.degraded, []);
  });
});

test('a refresh resumes on the scene the student stopped at', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, [
      { type: 'scene.create', sceneType: 'slide', title: 'A' },
      { type: 'scene.create', sceneType: 'slide', title: 'B' },
      { type: 'scene.create', sceneType: 'slide', title: 'C' },
    ]);
    const outline = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/outline`);
    const second = outline.body.scenes[1].id;

    const resumed = await call(base, 'GET', `${playbackPath(workspaceId, stageId)}?scene_id=${second}`);
    assert.equal(resumed.status, 200);
    assert.equal(resumed.body.start_index, 1);
    assert.equal(resumed.body.scenes[1].title, 'B');

    const missing = await call(base, 'GET', `${playbackPath(workspaceId, stageId)}?scene_id=scn_missing`);
    assert.equal(missing.status, 404);
  });
});

test('a scene with no renderable payload is listed as degraded, not silently dropped', async () => {
  const { server } = harness({ externalCdnAvailable: false });
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, [
      {
        type: 'scene.create',
        sceneType: 'interactive',
        title: '三维',
        content: { type: 'interactive', html: '<p>3d</p>', widgetType: 'visualization3d' },
      },
    ]);
    const plan = await call(base, 'GET', playbackPath(workspaceId, stageId));
    assert.equal(plan.body.scenes.length, 1);
    assert.equal(plan.body.scenes[0].render.kind, 'unsupported');
    assert.deepEqual(plan.body.degraded, [{ scene_id: plan.body.scenes[0].id, reason: 'widget_requires_external_cdn' }]);
  });
});

test('whiteboards and multi-agent configuration are reported per scene', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, [
      { type: 'scene.create', sceneType: 'slide', title: '带白板' },
    ]);
    const outline = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/outline`);
    const sceneId = outline.body.scenes[0].id;
    const revision = outline.body.revision;

    const updated = await call(
      base,
      'POST',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/commands`,
      {
        body: {
          commands: [{
            type: 'scene.update',
            sceneId,
            whiteboards: [{ id: 'wb_1' }],
            multiAgent: { enabled: true, agentIds: ['agent-1'] },
            actions: [{ id: 'a1', type: 'wb_open' }, { id: 'a2', type: 'discussion' }],
          }],
        },
        headers: { ...headers(), 'if-match': String(revision), 'idempotency-key': nextKey() },
      },
    );
    assert.equal(updated.status, 200, JSON.stringify(updated.body));

    const plan = await call(base, 'GET', playbackPath(workspaceId, stageId));
    assert.equal(plan.body.scenes[0].whiteboards, 1);
    assert.equal(plan.body.scenes[0].multi_agent, true);
    assert.deepEqual(plan.body.scenes[0].steps.map((step) => step.type), ['wb_open', 'discussion']);
  });
});

test("another user's stage has no playback plan", async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, [{ type: 'scene.create', sceneType: 'slide' }]);
    const denied = await call(base, 'GET', playbackPath(workspaceId, stageId), {
      headers: headers({ sub: 'user-2' }),
    });
    assert.equal(denied.status, 404);
  });
});

test('playback requires the stage read scope, and the service advertises player', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId } = await seedStage(base, [{ type: 'scene.create', sceneType: 'slide' }]);
    const denied = await call(base, 'GET', playbackPath(workspaceId, stageId), {
      headers: headers({ scopes: ['workspace:read'] }),
    });
    assert.equal(denied.status, 403);

    const ready = await fetch(`${base}/internal/health/ready`, {
      headers: headers({ scopes: ['service:status'] }),
    });
    const payload = await ready.json();
    assert.ok(payload.capabilities.includes('player'));
    assert.ok(payload.capabilities.includes('editor'));
  });
});
