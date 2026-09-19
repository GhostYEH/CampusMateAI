/**
 * Workspace + Stage persistence tests.
 *
 * The workspace layer is where "who may see this" and "what happens on a
 * concurrent edit" are decided, so the negative cases carry the weight here:
 * cross-user and cross-course reads, lost updates, replayed idempotency keys,
 * and cursors that try to escape their owner.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { DSL_VERSION, DSL_LIMITS } from '../src/dsl/index.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { MAX_REQUEST_BODY_BYTES } from '../src/server.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { mintAssertion, withServer, createHarness } from './helpers.mjs';

const WRITE_SCOPES = ['workspace:read', 'workspace:write'];

function harness() {
  const database = new ServiceDatabase(':memory:');
  const routes = createWorkspaceRoutes({ database });
  return { database, ...createHarness({ database, routes }) };
}

function headers({ sub = 'user-1', courseId = 'course-1', scopes = WRITE_SCOPES, extra = {} } = {}) {
  return {
    'x-campusmate-service-assertion': mintAssertion({ sub, courseId, scopes }),
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

async function createWorkspace(base, { name = '期末复习', description = '', key = 'k-1', ...rest } = {}) {
  return call(base, 'POST', '/internal/courses/course-1/workspaces', {
    body: { name, description },
    headers: headers({ extra: { 'idempotency-key': key }, ...rest }),
  });
}

// ===== create =====

test('creating a workspace returns 201 with a revision of 1', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    assert.equal(created.status, 201);
    assert.match(created.body.id, /^ws_/);
    assert.equal(created.body.name, '期末复习');
    assert.equal(created.body.course_id, 'course-1');
    assert.equal(created.body.revision, 1);
  });
});

test('a mutating request without an Idempotency-Key is refused', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await call(base, 'POST', '/internal/courses/course-1/workspaces', {
      body: { name: 'x' },
    });
    assert.equal(response.status, 400);
    assert.equal(response.body.error, 'invalid_request');
  });
});

test('a name is required and a non-object body is rejected', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const noName = await createWorkspace(base, { name: '   ' });
    assert.equal(noName.status, 400);

    const response = await fetch(`${base}/internal/courses/course-1/workspaces`, {
      method: 'POST',
      headers: headers({ extra: { 'idempotency-key': 'k-2' } }),
      body: '[1,2,3]',
    });
    assert.equal(response.status, 400);
  });
});

// ===== idempotency =====

test('replaying an idempotency key returns the stored response and creates one row', async () => {
  const { server, database } = harness();
  await withServer(server, async (base) => {
    const first = await createWorkspace(base, { key: 'same-key' });
    const second = await createWorkspace(base, { key: 'same-key' });
    assert.equal(second.status, 201);
    assert.deepEqual(second.body, first.body, 'a retry must not create a second workspace');

    const repository = new WorkspaceRepository(database);
    assert.equal(repository.listWorkspaces({ userId: 'user-1', courseId: 'course-1' }).items.length, 1);
  });
});

test('reusing a key with a different body is a conflict, not a silent overwrite', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    await createWorkspace(base, { key: 'reused', name: '第一次' });
    const conflicting = await createWorkspace(base, { key: 'reused', name: '第二次' });
    assert.equal(conflicting.status, 409);
    assert.equal(conflicting.body.error, 'idempotency_conflict');
  });
});

test('an idempotency key is scoped to its caller', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const mine = await createWorkspace(base, { key: 'shared-key', name: '我的' });
    const theirs = await createWorkspace(base, {
      key: 'shared-key',
      name: '别人的',
      sub: 'user-2',
    });
    assert.equal(theirs.status, 201);
    assert.notEqual(theirs.body.id, mine.body.id, 'two callers may use the same key independently');
  });
});

// ===== list + pagination =====

test('listing is keyset-paginated and clamps the limit', async () => {
  const { server, database } = harness();
  const repository = new WorkspaceRepository(database);
  for (let index = 0; index < 5; index += 1) {
    repository.createWorkspace({
      userId: 'user-1',
      courseId: 'course-1',
      name: `w${index}`,
      // Distinct timestamps keep the ordering deterministic without sleeping.
      now: `2026-01-0${index + 1}T00:00:00.000Z`,
    });
  }

  await withServer(server, async (base) => {
    const first = await call(base, 'GET', '/internal/courses/course-1/workspaces?limit=2');
    assert.equal(first.status, 200);
    assert.equal(first.body.items.length, 2);
    assert.equal(first.body.items[0].name, 'w4', 'newest first');
    assert.ok(first.body.next_cursor);

    const second = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces?limit=2&cursor=${encodeURIComponent(first.body.next_cursor)}`,
    );
    assert.deepEqual(second.body.items.map((item) => item.name), ['w2', 'w1']);
    assert.ok(second.body.next_cursor);

    const third = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces?limit=2&cursor=${encodeURIComponent(second.body.next_cursor)}`,
    );
    assert.deepEqual(third.body.items.map((item) => item.name), ['w0']);
    assert.equal(third.body.next_cursor, null, 'the last page must not promise more');

    // A limit above the ceiling is clamped rather than honoured or rejected.
    const clamped = await call(base, 'GET', `/internal/courses/course-1/workspaces?limit=5000`);
    assert.equal(clamped.body.items.length, 5);
  });
});

test('a cursor cannot be used to page past another user', async () => {
  const { server, database } = harness();
  const repository = new WorkspaceRepository(database);
  repository.createWorkspace({ userId: 'user-2', courseId: 'course-1', name: '别人的', now: '2026-01-01T00:00:00.000Z' });
  repository.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: '我的', now: '2026-01-02T00:00:00.000Z' });

  await withServer(server, async (base) => {
    const page = await call(base, 'GET', '/internal/courses/course-1/workspaces');
    assert.deepEqual(page.body.items.map((item) => item.name), ['我的']);

    // Forge a cursor that points past the other user's row.
    const forged = Buffer.from(JSON.stringify(['2026-01-01T00:00:00.000Z', 'whatever']), 'utf8').toString('base64url');
    const after = await call(base, 'GET', `/internal/courses/course-1/workspaces?cursor=${forged}`);
    assert.deepEqual(after.body.items, [], 'the cursor only narrows within the owner filter');
  });
});

test('a malformed cursor is ignored rather than fatal', async () => {
  const { server, database } = harness();
  new WorkspaceRepository(database).createWorkspace({ userId: 'user-1', courseId: 'course-1', name: 'w' });
  await withServer(server, async (base) => {
    const page = await call(base, 'GET', '/internal/courses/course-1/workspaces?cursor=not-base64!!');
    assert.equal(page.status, 200);
    assert.equal(page.body.items.length, 1);
  });
});

// ===== conditional update =====

test('updating requires If-Match and rejects a stale revision', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    const id = created.body.id;

    const missing = await call(base, 'PATCH', `/internal/courses/course-1/workspaces/${id}`, {
      body: { name: '新名字' },
    });
    assert.equal(missing.status, 400);

    const wildcard = await call(base, 'PATCH', `/internal/courses/course-1/workspaces/${id}`, {
      body: { name: '新名字' },
      headers: headers({ extra: { 'if-match': '*' } }),
    });
    assert.equal(wildcard.status, 400, 'If-Match: * is the lost update this header prevents');

    const updated = await call(base, 'PATCH', `/internal/courses/course-1/workspaces/${id}`, {
      body: { name: '新名字' },
      headers: headers({ extra: { 'if-match': '"1"' } }),
    });
    assert.equal(updated.status, 200);
    assert.equal(updated.body.name, '新名字');
    assert.equal(updated.body.revision, 2);

    const stale = await call(base, 'PATCH', `/internal/courses/course-1/workspaces/${id}`, {
      body: { name: '又改' },
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(stale.status, 412);
    assert.equal(stale.body.error, 'revision_mismatch');
  });
});

test('a stale revision on a deleted row reports not-found, not a retry loop', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    const id = created.body.id;
    await call(base, 'DELETE', `/internal/courses/course-1/workspaces/${id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    const after = await call(base, 'PATCH', `/internal/courses/course-1/workspaces/${id}`, {
      body: { name: 'x' },
      headers: headers({ extra: { 'if-match': '2' } }),
    });
    assert.equal(after.status, 404, 'retrying a revision conflict forever is worse than a 404');
  });
});

test('a patch with no updatable field is refused', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    const response = await call(base, 'PATCH', `/internal/courses/course-1/workspaces/${created.body.id}`, {
      body: {},
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(response.status, 400);
  });
});

// ===== soft delete =====

test('deleting a workspace hides it and its stages without reusing ids', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    const id = created.body.id;
    const stage = await call(base, 'POST', `/internal/courses/course-1/workspaces/${id}/stages`, {
      body: { title: '第一节' },
      headers: headers({ extra: { 'idempotency-key': 'stage-1' } }),
    });
    assert.equal(stage.status, 201);

    const deleted = await call(base, 'DELETE', `/internal/courses/course-1/workspaces/${id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(deleted.status, 200);

    assert.equal((await call(base, 'GET', `/internal/courses/course-1/workspaces/${id}`)).status, 404);
    const list = await call(base, 'GET', '/internal/courses/course-1/workspaces');
    assert.deepEqual(list.body.items, []);
    // The child must not stay reachable through its own id.
    const stageAfter = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${id}/stages/${stage.body.id}`,
    );
    assert.equal(stageAfter.status, 404);
  });
});

// ===== isolation =====

test('another user cannot read, update or delete a workspace', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    const id = created.body.id;
    // Every request needs its own assertion: a jti is single-use, so hoisting one
    // and reusing it would fail as a replay before ownership is even consulted.
    const asIntruder = (extra = {}) => headers({ sub: 'user-2', extra });

    assert.equal((await call(base, 'GET', `/internal/courses/course-1/workspaces/${id}`, {
      headers: asIntruder(),
    })).status, 404);
    assert.equal((await call(base, 'PATCH', `/internal/courses/course-1/workspaces/${id}`, {
      body: { name: 'x' },
      headers: asIntruder({ 'if-match': '1' }),
    })).status, 404);
    assert.equal((await call(base, 'DELETE', `/internal/courses/course-1/workspaces/${id}`, {
      headers: asIntruder({ 'if-match': '1' }),
    })).status, 404);
    const list = await call(base, 'GET', '/internal/courses/course-1/workspaces', { headers: asIntruder() });
    assert.deepEqual(list.body.items, []);
    // The owner's row is untouched by any of the above.
    assert.equal((await call(base, 'GET', `/internal/courses/course-1/workspaces/${id}`)).status, 200);
  });
});

test('reusing one assertion for two requests is rejected as a replay', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    const reused = headers();
    assert.equal((await call(base, 'GET', `/internal/courses/course-1/workspaces/${created.body.id}`, {
      headers: reused,
    })).status, 200);
    assert.equal((await call(base, 'GET', `/internal/courses/course-1/workspaces/${created.body.id}`, {
      headers: reused,
    })).status, 401, 'a jti is single-use even for a read');
  });
});

test('an assertion minted for another course cannot touch this course', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createWorkspace(base);
    const otherCourse = headers({ courseId: 'course-2' });
    const response = await call(base, 'GET', `/internal/courses/course-1/workspaces/${created.body.id}`, {
      headers: otherCourse,
    });
    assert.equal(response.status, 403);
  });
});

test('a missing write scope is forbidden', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await createWorkspace(base, {
      key: 'k',
      scopes: ['workspace:read'],
    });
    assert.equal(response.status, 403);
  });
});

// ===== stages =====

test('a stage is created empty, listed without its document and fetched with it', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const created = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      body: { title: '第一节' },
      headers: headers({ extra: { 'idempotency-key': 's-1' } }),
    });
    assert.equal(created.status, 201);
    assert.equal(created.body.dsl_version, DSL_VERSION);
    assert.deepEqual(created.body.document.scenes, []);

    const list = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`);
    assert.equal(list.body.items.length, 1);
    assert.equal(list.body.items[0].document, undefined, 'a list is a navigation surface, not a payload dump');

    const single = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${created.body.id}`,
    );
    assert.deepEqual(single.body.document.scenes, []);
  });
});

test('a stage document is validated on the way in', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const response = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      body: {
        title: '坏文档',
        document: {
          dslVersion: DSL_VERSION,
          stage: { id: 'stage-1', name: 'n', createdAt: 1, updatedAt: 2 },
          scenes: [{ id: 's', stageId: 'stage-1', type: 'hologram', title: 't', order: 0, content: {} }],
        },
      },
      headers: headers({ extra: { 'idempotency-key': 'bad-doc' } }),
    });
    assert.equal(response.status, 422);
    assert.equal(response.body.error, 'document_rejected');
    assert.ok(response.body.issues.some((item) => item.code === 'scene_type_invalid'));
  });
});

test('an oversize document is refused by name, not by the transport', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const response = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      body: { title: '太大', document: { huge: 'x'.repeat(DSL_LIMITS.maxDocumentBytes + 100) } },
      headers: headers({ extra: { 'idempotency-key': 'huge' } }),
    });
    assert.equal(response.status, 422);
    assert.equal(response.body.error, 'document_rejected');
    assert.equal(response.body.limit, 'maxDocumentBytes');
  });
});

test('the transport body cap sits above the document cap so neither hides the other', async () => {
  // If the transport cap were lower, an oversize document would be answered with
  // a generic 413 and the named limit below would never be exercised.
  assert.ok(
    MAX_REQUEST_BODY_BYTES > DSL_LIMITS.maxDocumentBytes,
    `transport cap ${MAX_REQUEST_BODY_BYTES} must exceed document cap ${DSL_LIMITS.maxDocumentBytes}`,
  );
});

test('a body above the transport cap is a 413', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const response = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      body: { title: '巨大', filler: 'x'.repeat(MAX_REQUEST_BODY_BYTES + 1024) },
      headers: headers({ extra: { 'idempotency-key': 'enormous' } }),
    });
    assert.equal(response.status, 413);
  });
});

test('replacing a stage is conditional and bumps the revision', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const stage = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      body: { title: '第一节' },
      headers: headers({ extra: { 'idempotency-key': 's-1' } }),
    });
    const path = `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${stage.body.id}`;

    const withoutDocument = await call(base, 'PUT', path, {
      body: { title: '改标题' },
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(withoutDocument.status, 400);

    const replaced = await call(base, 'PUT', path, {
      body: {
        title: '改标题',
        document: {
          dslVersion: DSL_VERSION,
          stage: { id: 'stage-1', name: '演示', createdAt: 1, updatedAt: 2 },
          scenes: [{
            id: 'scene-1',
            stageId: 'stage-1',
            type: 'interactive',
            title: '模拟',
            order: 0,
            content: { type: 'interactive', html: '<meta http-equiv="refresh" content="0"><b>ok</b>', widgetType: 'simulation' },
          }],
        },
      },
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(replaced.status, 200);
    assert.equal(replaced.body.revision, 2);
    assert.equal(replaced.body.title, '改标题');
    // Sanitization is applied on the write path, not left to the renderer.
    assert.doesNotMatch(replaced.body.document.scenes[0].content.html, /http-equiv/i);

    const stale = await call(base, 'PUT', path, {
      body: { document: { stage: { id: 'x', name: 'n', createdAt: 1, updatedAt: 2 }, scenes: [] } },
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(stale.status, 412);
  });
});

test('a stage cannot be reached through another workspace id', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const first = await createWorkspace(base, { key: 'a', name: 'A' });
    const second = await createWorkspace(base, { key: 'b', name: 'B' });
    const stage = await call(base, 'POST', `/internal/courses/course-1/workspaces/${first.body.id}/stages`, {
      body: { title: '第一节' },
      headers: headers({ extra: { 'idempotency-key': 's-1' } }),
    });
    const crossed = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${second.body.id}/stages/${stage.body.id}`,
    );
    assert.equal(crossed.status, 404, 'a stage id must not be usable across workspaces');
  });
});

test('stages of another user are invisible even with a known workspace id', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      body: { title: '第一节' },
      headers: headers({ extra: { 'idempotency-key': 's-1' } }),
    });
    const list = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`,
      { headers: headers({ sub: 'user-2' }) },
    );
    assert.equal(list.status, 404);
  });
});

test('a stage is deleted softly and stops appearing', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const stage = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      body: { title: '第一节' },
      headers: headers({ extra: { 'idempotency-key': 's-1' } }),
    });
    const path = `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${stage.body.id}`;

    assert.equal((await call(base, 'DELETE', path, { headers: headers({ extra: { 'if-match': '1' } }) })).status, 200);
    assert.equal((await call(base, 'GET', path)).status, 404);
    const list = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`);
    assert.deepEqual(list.body.items, []);
    assert.equal((await call(base, 'DELETE', path, { headers: headers({ extra: { 'if-match': '1' } }) })).status, 404);
  });
});

test('the workspace capability is advertised exactly once', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await fetch(`${base}/internal/health/ready`, {
      headers: { 'x-campusmate-service-assertion': mintAssertion({ scopes: ['service:status'] }) },
    });
    const body = await response.json();
    assert.deepEqual(body.capabilities, ['workspace']);
  });
});

test('an unknown workspace id is a plain 404 without an existence oracle', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await call(base, 'GET', '/internal/courses/course-1/workspaces/ws_does_not_exist');
    assert.equal(response.status, 404);
    assert.equal(response.body.error, 'not_found');
    assert.equal(JSON.stringify(response.body).includes('ws_does_not_exist'), false, 'no echo of the input');
  });
});

test('concurrent writers: only one of two same-revision updates wins', async () => {
  const { database } = harness();
  const repository = new WorkspaceRepository(database);
  const workspace = repository.createWorkspace({ userId: 'user-1', courseId: 'course-1', name: 'w' });

  const first = repository.updateWorkspace({
    userId: 'user-1', courseId: 'course-1', workspaceId: workspace.id,
    expectedRevision: 1, patch: { name: 'A' },
  });
  assert.equal(first.revision, 2);

  assert.throws(() => repository.updateWorkspace({
    userId: 'user-1', courseId: 'course-1', workspaceId: workspace.id,
    expectedRevision: 1, patch: { name: 'B' },
  }), (error) => {
    assert.equal(error.code, 'revision_mismatch');
    return true;
  });
  assert.equal(repository.getWorkspace({ userId: 'user-1', courseId: 'course-1', workspaceId: workspace.id }).name, 'A');
});
