/**
 * Editor command tests.
 *
 * The editor is the one place where two authors can hold the same document, so
 * these tests are weighted towards the cases that corrupt content rather than the
 * happy path: a part-applied command list, an `order` sequence that develops
 * holes, a command that silently changes a scene's type, and a retry that
 * duplicates a scene.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { DSL_LIMITS } from '../src/dsl/index.ts';
import { applyStageCommands, DslCommandError } from '../src/dsl/commands.ts';
import { createEditorRoutes } from '../src/editor/routes.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';
import { mintAssertion, withServer, createHarness } from './helpers.mjs';

const SCOPES = ['workspace:read', 'workspace:write', 'stage:read', 'stage:write'];

function harness() {
  const database = new ServiceDatabase(':memory:');
  const routes = [...createWorkspaceRoutes({ database }), ...createEditorRoutes({ database })];
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
const nextKey = () => `k-${(keyCounter += 1)}`;

async function seedStage(base, { sub = 'user-1' } = {}) {
  const workspace = await call(base, 'POST', '/internal/courses/course-1/workspaces', {
    body: { name: '编辑测试' },
    headers: headers({ sub, extra: { 'idempotency-key': nextKey() } }),
  });
  const stage = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
    body: { title: '第一课' },
    headers: headers({ sub, extra: { 'idempotency-key': nextKey() } }),
  });
  return { workspaceId: workspace.body.id, stageId: stage.body.id, revision: stage.body.revision };
}

function commandsPath(workspaceId, stageId) {
  return `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/commands`;
}

function command(sceneType = 'slide', overrides = {}) {
  return { type: 'scene.create', sceneType, title: `${sceneType} 场景`, ...overrides };
}

// ===== 命令层（纯函数） =====

function aggregate() {
  return {
    dslVersion: '0.3.0',
    stage: { id: 'stg_1', name: '第一课', createdAt: 1, updatedAt: 1 },
    scenes: [],
  };
}

test('a scene.create fills in the minimal valid content for its type', () => {
  const next = applyStageCommands(aggregate(), [{ type: 'scene.create', sceneType: 'slide' }], { now: 5 });
  assert.equal(next.scenes.length, 1);
  assert.equal(next.scenes[0].type, 'slide');
  assert.equal(next.scenes[0].stageId, 'stg_1');
  assert.equal(next.scenes[0].order, 0);
  assert.deepEqual(next.scenes[0].content, { type: 'slide', canvas: {} });
});

test('an interactive scene cannot be created without html or url', () => {
  assert.throws(
    () => applyStageCommands(aggregate(), [{ type: 'scene.create', sceneType: 'interactive' }]),
    (error) => error instanceof DslCommandError && error.code === 'interactive_content_required',
  );
});

test('orders stay dense after create, move and delete', () => {
  let next = applyStageCommands(aggregate(), [
    { type: 'scene.create', sceneType: 'slide' },
    { type: 'scene.create', sceneType: 'quiz' },
    { type: 'scene.create', sceneType: 'pbl' },
  ]);
  assert.deepEqual(next.scenes.map((scene) => scene.order), [0, 1, 2]);

  next = applyStageCommands(next, [{ type: 'scene.move', sceneId: next.scenes[2].id, toIndex: 0 }]);
  assert.deepEqual(next.scenes.map((scene) => scene.order), [0, 1, 2]);
  assert.equal(next.scenes[0].type, 'pbl');

  next = applyStageCommands(next, [{ type: 'scene.delete', sceneId: next.scenes[0].id }]);
  assert.deepEqual(next.scenes.map((scene) => scene.order), [0, 1]);
});

test('a duplicate deep-copies its payload so editing the copy cannot reach the original', () => {
  const first = applyStageCommands(aggregate(), [
    { type: 'scene.create', sceneType: 'quiz' },
  ]);
  const withCopy = applyStageCommands(first, [
    { type: 'scene.duplicate', sceneId: first.scenes[0].id },
  ]);
  assert.equal(withCopy.scenes.length, 2);
  assert.notEqual(withCopy.scenes[0].id, withCopy.scenes[1].id);
  assert.notEqual(withCopy.scenes[0].content, withCopy.scenes[1].content);
  assert.match(withCopy.scenes[1].title, /副本/);
});

test('a scene.update may not change the scene type', () => {
  const first = applyStageCommands(aggregate(), [{ type: 'scene.create', sceneType: 'slide' }]);
  assert.throws(
    () => applyStageCommands(first, [{
      type: 'scene.update',
      sceneId: first.scenes[0].id,
      content: { type: 'quiz', questions: [] },
    }]),
    (error) => error instanceof DslCommandError && error.code === 'content_type_mismatch',
  );
});

test('slide.element.move changes only the target coordinates and keeps actions', () => {
  const document = {
    ...aggregate(),
    scenes: [{
      id: 'slide_1',
      stageId: 'stg_1',
      title: '画布',
      order: 0,
      type: 'slide',
      actions: [{ id: 'act_1', type: 'speech', text: '保留' }],
      content: {
        type: 'slide',
        canvas: {
          width: 1000,
          height: 562.5,
          elements: [
            { id: 'el_1', type: 'text', left: 10, top: 20, width: 100, height: 40, content: 'A' },
            { id: 'el_2', type: 'shape', left: 30, top: 40, width: 20, height: 20 },
          ],
        },
      },
    }],
  };
  const next = applyStageCommands(document, [{
    type: 'slide.element.move', sceneId: 'slide_1', elementId: 'el_1', left: 110.5, top: 220.25,
  }]);
  assert.deepEqual(next.scenes[0].content.canvas.elements[0], {
    id: 'el_1', type: 'text', left: 110.5, top: 220.25, width: 100, height: 40, content: 'A',
  });
  assert.deepEqual(next.scenes[0].content.canvas.elements[1], document.scenes[0].content.canvas.elements[1]);
  assert.deepEqual(next.scenes[0].actions, document.scenes[0].actions);
  assert.equal(next.scenes[0].order, document.scenes[0].order);
});

test('slide.element.move rejects unknown targets, non-slide scenes, and non-finite coordinates', () => {
  const document = {
    ...aggregate(),
    scenes: [
      {
        id: 'slide_1', stageId: 'stg_1', title: '幻灯片', order: 0, type: 'slide',
        content: { type: 'slide', canvas: { elements: [{ id: 'el_1', left: 1, top: 2 }] } },
      },
      {
        id: 'quiz_1', stageId: 'stg_1', title: '测验', order: 1, type: 'quiz',
        content: { type: 'quiz', questions: [] },
      },
    ],
  };
  assert.throws(
    () => applyStageCommands(document, [{ type: 'slide.element.move', sceneId: 'missing', elementId: 'el_1', left: 1, top: 2 }]),
    (error) => error instanceof DslCommandError && error.code === 'scene_not_found',
  );
  assert.throws(
    () => applyStageCommands(document, [{ type: 'slide.element.move', sceneId: 'slide_1', elementId: 'missing', left: 1, top: 2 }]),
    (error) => error instanceof DslCommandError && error.code === 'element_not_found',
  );
  assert.throws(
    () => applyStageCommands(document, [{ type: 'slide.element.move', sceneId: 'quiz_1', elementId: 'el_1', left: 1, top: 2 }]),
    (error) => error instanceof DslCommandError && error.code === 'slide_element_requires_slide',
  );
  assert.throws(
    () => applyStageCommands(document, [{ type: 'slide.element.move', sceneId: 'slide_1', elementId: 'el_1', left: Number.NaN, top: 2 }]),
    (error) => error instanceof DslCommandError && error.code === 'command_field_invalid',
  );
  const missingPosition = structuredClone(document);
  missingPosition.scenes[0].content.canvas.elements[0] = { id: 'el_missing_position', type: 'shape' };
  assert.throws(
    () => applyStageCommands(missingPosition, [{
      type: 'slide.element.move', sceneId: 'slide_1', elementId: 'el_missing_position', left: 1, top: 2,
    }]),
    (error) => error instanceof DslCommandError
      && error.code === 'element_position_invalid'
      && error.path === 'commands[0].elementId',
  );
  const nonFinitePosition = structuredClone(document);
  nonFinitePosition.scenes[0].content.canvas.elements[0].top = Number.POSITIVE_INFINITY;
  assert.throws(
    () => applyStageCommands(nonFinitePosition, [{
      type: 'slide.element.move', sceneId: 'slide_1', elementId: 'el_1', left: 1, top: 2,
    }]),
    (error) => error instanceof DslCommandError
      && error.code === 'element_position_invalid'
      && error.path === 'commands[0].elementId',
  );
});

test('an unknown command or a missing scene is refused before anything is applied', () => {
  const first = applyStageCommands(aggregate(), [{ type: 'scene.create', sceneType: 'slide' }]);
  assert.throws(
    () => applyStageCommands(first, [
      { type: 'scene.create', sceneType: 'slide' },
      { type: 'scene.explode', sceneId: 'x' },
    ]),
    (error) => error instanceof DslCommandError && error.code === 'command_type_invalid',
  );
  assert.throws(
    () => applyStageCommands(first, [{ type: 'scene.delete', sceneId: 'scn_missing' }]),
    (error) => error instanceof DslCommandError && error.code === 'scene_not_found',
  );
  assert.throws(
    () => applyStageCommands(first, [{ type: 'scene.move', sceneId: first.scenes[0].id, toIndex: 4 }]),
    (error) => error instanceof DslCommandError && error.code === 'scene_move_out_of_range',
  );
});

test('a command list longer than the declared limit is a named limit violation', () => {
  const many = Array.from({ length: DSL_LIMITS.maxCommandsPerRequest + 1 }, () => ({
    type: 'scene.create',
    sceneType: 'slide',
  }));
  assert.throws(() => applyStageCommands(aggregate(), many), /maxCommandsPerRequest/);
});

// ===== HTTP 边界 =====

test('applying a command list stores the result and bumps the revision', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    const response = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command('slide'), command('quiz')] },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    assert.equal(response.status, 200);
    assert.equal(response.body.revision, revision + 1);
    assert.equal(response.body.applied_commands, 2);
    assert.equal(response.body.document.scenes.length, 2);
    assert.deepEqual(response.body.document.scenes.map((scene) => scene.order), [0, 1]);
  });
});

test('an HTTP element move persists coordinates and leaves the scene timeline untouched', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    const created = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: {
        commands: [{
          type: 'scene.create', sceneType: 'slide', title: '可拖拽',
          content: {
            type: 'slide',
            canvas: { width: 1000, height: 562.5, elements: [{ id: 'el_drag', type: 'text', left: 40, top: 50, width: 200, height: 60, content: '拖动我' }] },
          },
          actions: [{ id: 'act_1', type: 'speech', text: '时间线不应丢失' }],
        }],
      },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    assert.equal(created.status, 200);
    const sceneId = created.body.document.scenes[0].id;
    const moved = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [{ type: 'slide.element.move', sceneId, elementId: 'el_drag', left: 140.25, top: 87.5 }] },
      headers: headers({ extra: { 'if-match': String(created.body.revision), 'idempotency-key': nextKey() } }),
    });
    assert.equal(moved.status, 200);
    const scene = moved.body.document.scenes[0];
    assert.deepEqual(scene.content.canvas.elements[0].left, 140.25);
    assert.deepEqual(scene.content.canvas.elements[0].top, 87.5);
    assert.deepEqual(scene.actions, [{ id: 'act_1', type: 'speech', text: '时间线不应丢失' }]);
  });
});

test('an editor write requires both If-Match and an Idempotency-Key', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);

    const noMatch = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command()] },
      headers: headers({ extra: { 'idempotency-key': nextKey() } }),
    });
    assert.equal(noMatch.status, 400);

    const noKey = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command()] },
      headers: headers({ extra: { 'if-match': String(revision) } }),
    });
    assert.equal(noKey.status, 400);
  });
});

test('replaying the same idempotency key does not create a second scene', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    const key = nextKey();
    const send = () => call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command('slide')] },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': key } }),
    });

    const first = await send();
    const replay = await send();
    assert.equal(first.status, 200);
    assert.equal(replay.status, 200);
    assert.equal(replay.body.revision, first.body.revision);
    assert.equal(replay.body.document.scenes.length, 1);

    const outline = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/outline`,
    );
    assert.equal(outline.body.scenes.length, 1);
  });
});

test('a stale revision is a conflict and the document is left untouched', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command('slide')] },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    const stale = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command('quiz')] },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    assert.equal(stale.status, 412);

    const outline = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/outline`,
    );
    assert.equal(outline.body.scenes.length, 1, '失败的命令不得留下半个文档');
    assert.equal(outline.body.scenes[0].type, 'slide');
  });
});

test('a rejected command answers 422 with a machine-readable code and path', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    const response = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [{ type: 'scene.create', sceneType: 'interactive' }] },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    assert.equal(response.status, 422);
    assert.equal(response.body.error, 'command_rejected');
    assert.equal(response.body.code, 'interactive_content_required');
    assert.equal(response.body.path, 'commands[0].content');
  });
});

test('an empty command list is refused rather than treated as a no-op save', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    const response = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [] },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    assert.equal(response.status, 400);
  });
});

test("another user's stage is a plain 404 and cannot be edited or listed", async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);

    const outline = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/outline`,
      { headers: headers({ sub: 'user-2' }) },
    );
    assert.equal(outline.status, 404);

    const edit = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command()] },
      headers: headers({ sub: 'user-2', extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    assert.equal(edit.status, 404);
  });
});

test('the outline omits scene content but keeps what a sidebar renders', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: {
        commands: [{
          type: 'scene.create',
          sceneType: 'slide',
          content: { type: 'slide', canvas: { blocks: [{ kind: 'text', text: '很长的正文' }] } },
          actions: [{ id: 'act_1', type: 'speech', text: '讲解' }],
        }],
      },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });

    const outline = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/outline`,
    );
    assert.equal(outline.status, 200);
    assert.equal(outline.body.scenes.length, 1);
    assert.equal(outline.body.scenes[0].actions, 1);
    assert.equal(outline.body.scenes[0].content, undefined, '大纲不得携带场景正文');
    assert.equal(JSON.stringify(outline.body).includes('很长的正文'), false);
  });
});

test('a single scene can be read back by id, and an unknown id is a 404', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    const applied = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command('slide')] },
      headers: headers({ extra: { 'if-match': String(revision), 'idempotency-key': nextKey() } }),
    });
    const sceneId = applied.body.document.scenes[0].id;

    const found = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/scenes/${sceneId}`,
    );
    assert.equal(found.status, 200);
    assert.equal(found.body.content.type, 'slide');

    const missing = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspaceId}/stages/${stageId}/scenes/scn_missing`,
    );
    assert.equal(missing.status, 404);
  });
});

test('editing requires the stage write scope, and the service advertises editor', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const { workspaceId, stageId, revision } = await seedStage(base);
    const denied = await call(base, 'POST', commandsPath(workspaceId, stageId), {
      body: { commands: [command()] },
      headers: headers({
        scopes: ['workspace:read'],
        extra: { 'if-match': String(revision), 'idempotency-key': nextKey() },
      }),
    });
    assert.equal(denied.status, 403);

    const ready = await fetch(`${base}/internal/health/ready`, {
      headers: headers({ scopes: ['service:status'] }),
    });
    const payload = await ready.json();
    assert.ok(payload.capabilities.includes('editor'));
  });
});
