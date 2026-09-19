import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { createWhiteboardRoutes } from '../src/whiteboard/routes.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const SCOPES = ['stage:read', 'stage:write'];

function headers({ sub = 'user-1', courseId = 'course-1', scopes = SCOPES, extra = {} } = {}) {
  return { 'x-campusmate-service-assertion': mintAssertion({ sub, courseId, scopes }), 'content-type': 'application/json', ...extra };
}

async function call(base, method, path, { body, ...options } = {}) {
  const response = await fetch(`${base}${path}`, { method, headers: options.headers ?? headers(), ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : null };
}

function harness() {
  const database = new ServiceDatabase(':memory:');
  const repository = new WorkspaceRepository(database);
  const workspace = repository.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '白板工作台' });
  const stage = repository.createStage({ userId: 'user-1', courseId: 'course-1', workspaceId: workspace.id, title: '第一场', document: { stage: { id: 'stage-1', name: '第一场', createdAt: 1, updatedAt: 1 }, scenes: [] }, dslVersion: '0.3.0' });
  return { workspace, stage, ...createHarness({ database, routes: createWhiteboardRoutes({ database }) }) };
}

test('whiteboard writes a bounded board into the owned stage and survives a read', async () => {
  const { server, workspace, stage } = harness();
  await withServer(server, async (base) => {
    const result = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.id}/stages/${stage.id}/whiteboard`, {
      body: { board: { id: 'board-1', title: '推导', elements: [{ type: 'text', text: '极限' }] } },
      headers: headers({ extra: { 'if-match': '1', 'idempotency-key': 'board-1' } }),
    });
    assert.equal(result.status, 200);
    assert.equal(result.body.revision, 2);
    assert.equal(result.body.document.stage.whiteboard[0].id, 'board-1');
    assert.equal(result.body.document.stage.whiteboard[0].elements[0].text, '极限');
  });
});

test('whiteboard rejects unsafe or foreign writes without changing the stage', async () => {
  const { server, workspace, stage } = harness();
  await withServer(server, async (base) => {
    const invalid = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.id}/stages/${stage.id}/whiteboard`, {
      body: { board: { id: 'board-1', title: 'x', elements: 'not-an-array' } },
      headers: headers({ extra: { 'if-match': '1', 'idempotency-key': 'invalid-board' } }),
    });
    assert.equal(invalid.status, 400);
    const foreign = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.id}/stages/${stage.id}/whiteboard`, {
      body: { board: { id: 'board-2', title: 'x', elements: [] } },
      headers: headers({ sub: 'user-2', extra: { 'if-match': '1', 'idempotency-key': 'foreign-board' } }),
    });
    assert.equal(foreign.status, 404);
  });
});
