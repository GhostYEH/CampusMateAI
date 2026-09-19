import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { createGenerationRoutes } from '../src/generation/routes.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const SCOPES = ['workspace:read', 'workspace:write', 'job:read', 'job:write', 'generation:write'];

function headers({ sub = 'user-1', courseId = 'course-1', extra = {} } = {}) {
  return {
    'x-campusmate-service-assertion': mintAssertion({ sub, courseId, scopes: SCOPES }),
    'content-type': 'application/json',
    ...extra,
  };
}

async function call(base, method, path, { body, ...options } = {}) {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: options.headers ?? headers(),
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : null };
}

function harness() {
  const database = new ServiceDatabase(':memory:');
  const workspace = new WorkspaceRepository(database).createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '微积分复习' });
  return { workspace, ...createHarness({ database, routes: createGenerationRoutes({ database }) }) };
}

test('generation creates a real persisted stage for every supported mode', async () => {
  const modes = ['slide', 'quiz', 'interactive', 'pbl', 'simulation', 'diagram', 'code', 'game', 'visualization3d', 'procedural-skill'];
  const { server, workspace } = harness();
  await withServer(server, async (base) => {
    for (const [index, mode] of modes.entries()) {
      const result = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.id}/generate`, {
        body: { mode, prompt: `关于${mode}的学习内容` },
        headers: headers({ extra: { 'idempotency-key': `generate-${mode}` } }),
      });
      assert.equal(result.status, 201, mode);
      assert.equal(result.body.job.status, 'completed', mode);
      assert.equal(result.body.stage.document.scenes.length, 1, mode);
      assert.equal(result.body.stage.document.scenes[0].title, `关于${mode}的学习内容`, mode);
      assert.equal(result.body.stage.document.scenes[0].order, 0, mode);
      assert.equal(result.body.stage_id, result.body.stage.id, mode);
      assert.equal(result.body.job.progress, 100, mode);
      assert.equal(index >= 0, true);
    }
  });
});

test('generation rejects unknown modes and does not create a stage', async () => {
  const { server, workspace, database } = harness();
  await withServer(server, async (base) => {
    const result = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.id}/generate`, {
      body: { mode: 'secret-mode', prompt: 'x' },
      headers: headers({ extra: { 'idempotency-key': 'bad-mode' } }),
    });
    assert.equal(result.status, 400);
    const count = database.raw.prepare('SELECT count(*) AS count FROM stages').get();
    assert.equal(Number(count.count), 0);
  });
});

test('generation is isolated by workspace ownership and course', async () => {
  const { server, workspace } = harness();
  await withServer(server, async (base) => {
    const user = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.id}/generate`, {
      body: { mode: 'slide', prompt: 'x' },
      headers: headers({ sub: 'user-2', extra: { 'idempotency-key': 'cross-user' } }),
    });
    assert.equal(user.status, 404);
    const course = await call(base, 'POST', `/internal/courses/course-2/workspaces/${workspace.id}/generate`, {
      body: { mode: 'slide', prompt: 'x' },
      headers: headers({ courseId: 'course-2', extra: { 'idempotency-key': 'cross-course' } }),
    });
    assert.equal(course.status, 404);
  });
});
