/**
 * Folder + search tests.
 *
 * Discovery is the surface where "whose content is this" is easiest to get
 * wrong: a folder tree is navigated by id, and a search runs over every stage a
 * student owns. Both modules therefore decide ownership in the SQL predicate
 * rather than in the handler, and these tests pin that: a foreign folder id, a
 * foreign course, and a foreign user must all be indistinguishable from "does
 * not exist", and search must never surface a row the caller cannot open.
 */
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { MIGRATIONS } from '../src/db/migrations.ts';
import { createDiscoveryRoutes } from '../src/discovery/routes.ts';
import { WorkspaceRepository } from '../src/workspace/repository.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';
import { mintAssertion, withServer, createHarness } from './helpers.mjs';

const SCOPES = [
  'folder:read',
  'folder:write',
  'search:read',
  'workspace:read',
  'workspace:write',
];

function harness() {
  const database = new ServiceDatabase(':memory:');
  const routes = [...createWorkspaceRoutes({ database }), ...createDiscoveryRoutes({ database })];
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
function nextKey(prefix) {
  keyCounter += 1;
  return `${prefix}-${keyCounter}`;
}

function createFolder(base, { name = '第一章', parentId, sub = 'user-1' } = {}) {
  return call(base, 'POST', '/internal/courses/course-1/folders', {
    body: { name, ...(parentId === undefined ? {} : { parent_id: parentId }) },
    headers: headers({ sub, extra: { 'idempotency-key': nextKey('folder') } }),
  });
}

function createWorkspace(base, { name = '期末复习', description = '', folderId, sub = 'user-1' } = {}) {
  return call(base, 'POST', '/internal/courses/course-1/workspaces', {
    body: { name, description, ...(folderId === undefined ? {} : { folder_id: folderId }) },
    headers: headers({ sub, extra: { 'idempotency-key': nextKey('ws') } }),
  });
}

function createStage(base, workspaceId, { title = '第一课', sub = 'user-1' } = {}) {
  return call(base, 'POST', `/internal/courses/course-1/workspaces/${workspaceId}/stages`, {
    body: { title },
    headers: headers({ sub, extra: { 'idempotency-key': nextKey('stage') } }),
  });
}

// ===== folders: happy path =====

test('a new folder starts at revision 1 and lists with an empty workspace count', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await createFolder(base, { name: '第一章' });
    assert.equal(created.status, 201);
    assert.match(created.body.id, /^fd_/);
    assert.equal(created.body.name, '第一章');
    assert.equal(created.body.course_id, 'course-1');
    assert.equal(created.body.parent_id, null);
    assert.equal(created.body.revision, 1);

    const listed = await call(base, 'GET', '/internal/courses/course-1/folders');
    assert.equal(listed.status, 200);
    assert.equal(listed.body.items.length, 1);
    assert.equal(listed.body.items[0].workspace_count, 0);
  });
});

test('a folder create without an Idempotency-Key is refused, and a replay returns the first answer', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const missing = await call(base, 'POST', '/internal/courses/course-1/folders', {
      body: { name: 'x' },
    });
    assert.equal(missing.status, 400);
    assert.equal(missing.body.error, 'invalid_request');

    const key = 'folder-replay';
    const first = await call(base, 'POST', '/internal/courses/course-1/folders', {
      body: { name: '第二章' },
      headers: headers({ extra: { 'idempotency-key': key } }),
    });
    const replay = await call(base, 'POST', '/internal/courses/course-1/folders', {
      body: { name: '第二章' },
      headers: headers({ extra: { 'idempotency-key': key } }),
    });
    assert.equal(replay.status, first.status);
    assert.equal(replay.body.id, first.body.id);
  });
});

test('a nested folder keeps its parent and the tree lists newest first', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const parent = await createFolder(base, { name: '第一章' });
    const child = await createFolder(base, { name: '第一节', parentId: parent.body.id });
    assert.equal(child.status, 201);
    assert.equal(child.body.parent_id, parent.body.id);

    const listed = await call(base, 'GET', '/internal/courses/course-1/folders');
    assert.deepEqual(
      listed.body.items.map((item) => item.name).sort(),
      ['第一章', '第一节'],
    );
  });
});

test('a folder cannot be reparented under itself or under one of its descendants', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const parent = await createFolder(base, { name: 'A' });
    const child = await createFolder(base, { name: 'B', parentId: parent.body.id });

    const underItself = await call(base, 'PATCH', `/internal/courses/course-1/folders/${parent.body.id}`, {
      body: { parent_id: parent.body.id },
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(underItself.status, 400);

    const underChild = await call(base, 'PATCH', `/internal/courses/course-1/folders/${parent.body.id}`, {
      body: { parent_id: child.body.id },
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(underChild.status, 400);
  });
});

test('renaming a folder without If-Match is refused and a stale revision is a conflict', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const folder = await createFolder(base, { name: 'old' });

    const noMatch = await call(base, 'PATCH', `/internal/courses/course-1/folders/${folder.body.id}`, {
      body: { name: 'new' },
    });
    assert.equal(noMatch.status, 400);
    assert.equal(noMatch.body.error, 'invalid_request');

    const stale = await call(base, 'PATCH', `/internal/courses/course-1/folders/${folder.body.id}`, {
      body: { name: 'new' },
      headers: headers({ extra: { 'if-match': '9' } }),
    });
    // 412 at the service boundary; the gateway turns it into 409 for the browser.
    assert.equal(stale.status, 412);

    const wildcard = await call(base, 'PATCH', `/internal/courses/course-1/folders/${folder.body.id}`, {
      body: { name: 'new' },
      headers: headers({ extra: { 'if-match': '*' } }),
    });
    assert.equal(wildcard.status, 400);

    const ok = await call(base, 'PATCH', `/internal/courses/course-1/folders/${folder.body.id}`, {
      body: { name: 'new' },
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(ok.status, 200);
    assert.equal(ok.body.name, 'new');
    assert.equal(ok.body.revision, 2);
  });
});

test('deleting a folder unfiles its workspaces instead of hiding them', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const folder = await createFolder(base, { name: '临时' });
    const workspace = await createWorkspace(base, { name: '归档内容', folderId: folder.body.id });
    assert.equal(workspace.status, 201);
    assert.equal(workspace.body.folder_id, folder.body.id);

    const counted = await call(base, 'GET', '/internal/courses/course-1/folders');
    assert.equal(counted.body.items[0].workspace_count, 1);

    const deleted = await call(base, 'DELETE', `/internal/courses/course-1/folders/${folder.body.id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(deleted.status, 200);

    const listed = await call(base, 'GET', '/internal/courses/course-1/folders');
    assert.equal(listed.body.items.length, 0);

    const stillThere = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspace.body.id}`,
    );
    assert.equal(stillThere.status, 200);
    assert.equal(stillThere.body.folder_id, null);
  });
});

test('a workspace may only be filed into a folder the same caller owns in the same course', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const foreign = await createFolder(base, { name: '别人的', sub: 'user-2' });
    assert.equal(foreign.status, 201);

    const misfiled = await createWorkspace(base, { name: 'x', folderId: foreign.body.id });
    assert.equal(misfiled.status, 404);
    assert.equal(misfiled.body.error, 'not_found');
  });
});

// ===== folders: ownership =====

test('a folder owned by another user is a plain 404, not an existence oracle', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const folder = await createFolder(base, { name: '私密' });
    const read = await call(base, 'GET', `/internal/courses/course-1/folders/${folder.body.id}`, {
      headers: headers({ sub: 'user-2' }),
    });
    assert.equal(read.status, 404);

    const patched = await call(base, 'PATCH', `/internal/courses/course-1/folders/${folder.body.id}`, {
      body: { name: 'hijack' },
      headers: headers({ sub: 'user-2', extra: { 'if-match': '1' } }),
    });
    assert.equal(patched.status, 404);

    const listed = await call(base, 'GET', '/internal/courses/course-1/folders', {
      headers: headers({ sub: 'user-2' }),
    });
    assert.deepEqual(listed.body.items, []);
  });
});

test('a folder from another course is invisible and the assertion course always wins', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const folder = await createFolder(base, { name: '课程一' });
    const otherCourse = await call(base, 'GET', '/internal/courses/course-2/folders', {
      headers: headers({ courseId: 'course-2' }),
    });
    assert.deepEqual(otherCourse.body.items, []);

    const crossCourse = await call(base, 'GET', '/internal/courses/course-2/folders', {
      headers: headers({ courseId: 'course-1' }),
    });
    assert.equal(crossCourse.status, 403);

    const foreignFolder = await call(base, 'GET', `/internal/courses/course-2/folders/${folder.body.id}`, {
      headers: headers({ courseId: 'course-2' }),
    });
    assert.equal(foreignFolder.status, 404);
  });
});

test('folder routes require the folder scope', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const noScope = await call(base, 'GET', '/internal/courses/course-1/folders', {
      headers: headers({ scopes: ['workspace:read'] }),
    });
    assert.equal(noScope.status, 403);
  });
});

// ===== search =====

test('search returns the caller own workspaces and stages with a站内深链', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base, { name: '线性代数复习' });
    const stage = await createStage(base, workspace.body.id, { title: '线性代数第一讲' });

    const found = await call(base, 'GET', '/internal/courses/course-1/search?q=线性代数');
    assert.equal(found.status, 200);
    const kinds = found.body.items.map((item) => item.kind).sort();
    assert.deepEqual(kinds, ['stage', 'workspace']);

    const stageHit = found.body.items.find((item) => item.kind === 'stage');
    assert.equal(stageHit.workspace_id, workspace.body.id);
    assert.equal(stageHit.stage_id, stage.body.id);
    assert.equal(
      stageHit.path,
      `/courses/course-1?tab=mentoring&workspace=${workspace.body.id}&stage=${stage.body.id}`,
    );
  });
});

test('search never returns another user row, even for an identical keyword', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    await createWorkspace(base, { name: '同名词条' });
    const otherUser = await call(base, 'GET', '/internal/courses/course-1/search?q=同名词条', {
      headers: headers({ sub: 'user-2' }),
    });
    assert.equal(otherUser.status, 200);
    assert.deepEqual(otherUser.body.items, []);
  });
});

test('search does not reach across courses or across soft-deleted rows', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base, { name: '可回收条目' });
    await createStage(base, workspace.body.id, { title: '可回收条目子项' });

    const otherCourse = await call(base, 'GET', '/internal/courses/course-2/search?q=可回收', {
      headers: headers({ courseId: 'course-2' }),
    });
    assert.deepEqual(otherCourse.body.items, []);

    await call(base, 'DELETE', `/internal/courses/course-1/workspaces/${workspace.body.id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    const afterDelete = await call(base, 'GET', '/internal/courses/course-1/search?q=可回收');
    assert.deepEqual(afterDelete.body.items, []);
  });
});

test('an empty, blank or overlong query is refused rather than answered with everything', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    await createWorkspace(base, { name: '任意内容' });

    for (const query of ['', '%20%20', '   ']) {
      const response = await call(base, 'GET', `/internal/courses/course-1/search?q=${query}`);
      assert.equal(response.status, 400, `query ${JSON.stringify(query)} must be refused`);
    }

    const missing = await call(base, 'GET', '/internal/courses/course-1/search');
    assert.equal(missing.status, 400);

    const long = await call(base, 'GET', `/internal/courses/course-1/search?q=${'a'.repeat(201)}`);
    assert.equal(long.status, 400);
  });
});

test('search treats the query as a literal, so a wildcard cannot widen it', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    await createWorkspace(base, { name: '百分比%内容' });
    const wildcard = await call(base, 'GET', '/internal/courses/course-1/search?q=%25');
    assert.deepEqual(
      wildcard.body.items.map((item) => item.title),
      ['百分比%内容'],
      'a bare % must match the literal character, not every row',
    );
    const underscore = await call(base, 'GET', '/internal/courses/course-1/search?q=_');
    assert.deepEqual(underscore.body.items, []);
  });
});

test('search pages deterministically and clamps an oversized limit', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    for (const name of ['分页条目一', '分页条目二', '分页条目三']) {
      await createWorkspace(base, { name });
    }
    const first = await call(base, 'GET', '/internal/courses/course-1/search?q=分页条目&limit=2');
    assert.equal(first.body.items.length, 2);
    assert.ok(first.body.next_cursor, 'a truncated page must hand back a cursor');

    const second = await call(
      base,
      'GET',
      `/internal/courses/course-1/search?q=分页条目&limit=2&cursor=${encodeURIComponent(first.body.next_cursor)}`,
    );
    assert.equal(second.body.items.length, 1);
    assert.equal(second.body.next_cursor, null);

    const clamped = await call(base, 'GET', '/internal/courses/course-1/search?q=分页条目&limit=500');
    assert.ok(clamped.body.items.length <= 50);
  });
});

test('search only returns rows the caller can still open', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base, { name: '目标条目' });
    const stage = await createStage(base, workspace.body.id, { title: '目标条目子项' });
    await call(base, 'DELETE', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${stage.body.id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });

    const found = await call(base, 'GET', '/internal/courses/course-1/search?q=目标条目');
    assert.deepEqual(
      found.body.items.map((item) => item.kind),
      ['workspace'],
      'a soft-deleted stage must not be handed back',
    );
  });
});

test('the service advertises folder and search only because these routes exist', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await fetch(`${base}/internal/health/ready`, {
      headers: headers({ scopes: ['service:status'] }),
    });
    const body = await response.json();
    assert.ok(body.capabilities.includes('folder'));
    assert.ok(body.capabilities.includes('search'));
  });
});

// ===== compatibility migration =====

test('a database created before folders existed upgrades without losing workspaces', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'omcf-migration-'));
  const path = join(directory, 'service.db');

  // Rebuild the pre-folder schema exactly as version 1 + 2 left it.
  const legacy = new DatabaseSync(path);
  legacy.exec(`CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at INTEGER NOT NULL
  )`);
  for (const migration of MIGRATIONS.filter((item) => item.version <= 2)) {
    for (const statement of migration.statements) legacy.exec(statement);
    legacy
      .prepare('INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)')
      .run(migration.version, migration.name, Date.now());
  }
  legacy
    .prepare(
      `INSERT INTO workspaces (id, user_id, course_id, name, description, revision, created_at, updated_at)
       VALUES ('ws_legacy', 'user-1', 'course-1', '旧工作台', '', 1, '2026-01-01T00:00:00.000Z', '2026-01-01T00:00:00.000Z')`,
    )
    .run();
  legacy.close();

  const upgraded = new ServiceDatabase(path);
  try {
    const applied = upgraded.raw
      .prepare('SELECT version FROM schema_migrations ORDER BY version')
      .all()
      .map((row) => Number(row.version));
    // Every declared migration ran exactly once, in order — including the ones
    // this fixture deliberately did not pre-apply. Comparing against the
    // declared list rather than a literal keeps this about "nothing was skipped
    // or re-run" instead of about how many migrations happen to exist today.
    assert.deepEqual(
      applied,
      MIGRATIONS.map((migration) => migration.version),
    );

    const repository = new WorkspaceRepository(upgraded);
    const row = repository.getWorkspace({ userId: 'user-1', courseId: 'course-1', workspaceId: 'ws_legacy' });
    assert.equal(row.name, '旧工作台');
    assert.equal(row.folder_id, null, 'a pre-folder row reads back as unfiled, not broken');
  } finally {
    upgraded.close();
  }
});
