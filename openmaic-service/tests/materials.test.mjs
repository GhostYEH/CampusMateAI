/**
 * Material tests.
 *
 * A material is the one place where the service stores text that came from a
 * file the student chose, so three things have to be true and are pinned here:
 *
 * 1. **Ownership is in the predicate, not the handler.** A foreign material id,
 *    a foreign course and a foreign user must all be indistinguishable from an
 *    id that never existed — including through the batch `resolve` endpoint,
 *    which is exactly the shape of query that leaks "this id exists" if it
 *    answers per-id instead of refusing the whole set.
 * 2. **A rejected payload is rejected by name.** An oversized byte size, a
 *    digest that is not a digest, or an `unsupported` extraction carrying text
 *    must be refused as `document_rejected`, not silently stored.
 * 3. **Uploading the same bytes twice is one material.** The digest is the
 *    identity for a live row, so a retry (or a re-selected file) dedupes rather
 *    than filling the course with copies.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { MIGRATIONS, SCHEMA_VERSION } from '../src/db/migrations.ts';
import {
  createMaterialRoutes,
  MAX_MATERIAL_BYTES,
  MAX_MATERIAL_TEXT_BYTES,
  MAX_REFERENCE_COUNT,
} from '../src/material/routes.ts';
import { MAX_REQUEST_BODY_BYTES } from '../src/server.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const SCOPES = ['material:read', 'material:write'];

const DIGEST = 'a'.repeat(64);
const OTHER_DIGEST = 'b'.repeat(64);

function harness() {
  const database = new ServiceDatabase(':memory:');
  const routes = createMaterialRoutes({ database });
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

function upload(base, { sub = 'user-1', courseId = 'course-1', key, ...overrides } = {}) {
  const payload = {
    filename: '讲义.md',
    media_type: 'text/markdown',
    byte_size: 1024,
    sha256: DIGEST,
    extraction_status: 'extracted',
    text: '# 第一章',
    ...overrides,
  };
  return call(base, 'POST', `/internal/courses/${courseId}/materials`, {
    body: payload,
    headers: headers({ sub, courseId, extra: { 'idempotency-key': key ?? nextKey('material') } }),
  });
}

// ===== happy path =====

test('a material uploads at revision 1 and lists without its text', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await upload(base);
    assert.equal(created.status, 201);
    assert.match(created.body.id, /^mt_/);
    assert.equal(created.body.filename, '讲义.md');
    assert.equal(created.body.course_id, 'course-1');
    assert.equal(created.body.revision, 1);
    assert.equal(created.body.deduplicated, false);
    assert.equal(created.body.text_chars, '# 第一章'.length);

    const listed = await call(base, 'GET', '/internal/courses/course-1/materials');
    assert.equal(listed.status, 200);
    assert.equal(listed.body.items.length, 1);
    // The list is a navigation surface; the text only travels on the one fetch
    // that is about to read it.
    assert.equal(listed.body.items[0].text, undefined);
    assert.equal(listed.body.items[0].text_chars, '# 第一章'.length);

    const fetched = await call(base, 'GET', `/internal/courses/course-1/materials/${created.body.id}`);
    assert.equal(fetched.status, 200);
    assert.equal(fetched.body.text, '# 第一章');
  });
});

test('a create without an Idempotency-Key is refused, and a replay returns the first answer', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const missing = await call(base, 'POST', '/internal/courses/course-1/materials', {
      body: {
        filename: 'x.md',
        media_type: 'text/markdown',
        byte_size: 1,
        sha256: DIGEST,
        extraction_status: 'extracted',
        text: 'x',
      },
    });
    assert.equal(missing.status, 400);
    assert.equal(missing.body.error, 'invalid_request');

    const key = 'material-replay';
    const first = await upload(base, { key, filename: '甲.md' });
    const replay = await upload(base, { key, filename: '甲.md' });
    assert.equal(replay.status, 201);
    assert.equal(replay.body.id, first.body.id);

    const listed = await call(base, 'GET', '/internal/courses/course-1/materials');
    assert.equal(listed.body.items.length, 1);
  });
});

test('uploading the same digest twice dedupes instead of cloning the material', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const first = await upload(base);
    const second = await upload(base, { filename: '讲义副本.md' });
    assert.equal(second.status, 201);
    assert.equal(second.body.id, first.body.id);
    assert.equal(second.body.deduplicated, true);
    // The first upload keeps its name: a later re-selection must not rename the
    // material a stage may already cite.
    assert.equal(second.body.filename, '讲义.md');

    const listed = await call(base, 'GET', '/internal/courses/course-1/materials');
    assert.equal(listed.body.items.length, 1);
  });
});

test('a different digest is a different material', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    await upload(base, { sha256: DIGEST });
    await upload(base, { sha256: OTHER_DIGEST });
    const listed = await call(base, 'GET', '/internal/courses/course-1/materials');
    assert.equal(listed.body.items.length, 2);
  });
});

// ===== ownership =====

test('another user cannot read, resolve or delete a material', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await upload(base, { sub: 'user-1' });
    const id = created.body.id;

    const read = await call(base, 'GET', `/internal/courses/course-1/materials/${id}`, {
      headers: headers({ sub: 'user-2' }),
    });
    assert.equal(read.status, 404);
    assert.equal(read.body.error, 'not_found');

    const resolved = await call(base, 'POST', '/internal/courses/course-1/materials/resolve', {
      body: { material_ids: [id] },
      headers: headers({ sub: 'user-2' }),
    });
    assert.equal(resolved.status, 200);
    assert.deepEqual(resolved.body.resolved, []);
    // A foreign id is reported as unresolved, not as "forbidden": the caller
    // learns nothing about whether it exists.
    assert.deepEqual(resolved.body.unresolved, [id]);

    const deleted = await call(base, 'DELETE', `/internal/courses/course-1/materials/${id}`, {
      headers: headers({ sub: 'user-2', extra: { 'if-match': '1' } }),
    });
    assert.equal(deleted.status, 404);

    const stillThere = await call(base, 'GET', `/internal/courses/course-1/materials/${id}`);
    assert.equal(stillThere.status, 200);
  });
});

test('a material cannot be reached through another course', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await upload(base, { courseId: 'course-1' });
    const read = await call(base, 'GET', `/internal/courses/course-2/materials/${created.body.id}`, {
      headers: headers({ courseId: 'course-2' }),
    });
    assert.equal(read.status, 404);
  });
});

test('the list is scoped to the caller and the course', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    await upload(base, { sub: 'user-1', courseId: 'course-1', sha256: DIGEST });
    await upload(base, { sub: 'user-1', courseId: 'course-2', sha256: DIGEST });
    await upload(base, { sub: 'user-2', courseId: 'course-1', sha256: DIGEST });

    const mine = await call(base, 'GET', '/internal/courses/course-1/materials');
    assert.equal(mine.body.items.length, 1);
    assert.equal(mine.body.items[0].id.startsWith('mt_'), true);

    const theirs = await call(base, 'GET', '/internal/courses/course-1/materials', {
      headers: headers({ sub: 'user-2' }),
    });
    assert.equal(theirs.body.items.length, 1);
    assert.notEqual(theirs.body.items[0].id, mine.body.items[0].id);
  });
});

// ===== payload policy =====

test('an oversized material is refused by name, below the transport cap', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const tooBig = await upload(base, { byte_size: MAX_MATERIAL_BYTES + 1 });
    assert.equal(tooBig.status, 422);
    assert.equal(tooBig.body.error, 'document_rejected');
  });
});

test('a digest that is not a sha256 is refused', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    for (const sha256 of ['ABC', 'a'.repeat(63), 'A'.repeat(64), 'z'.repeat(64)]) {
      const response = await upload(base, { sha256 });
      assert.equal(response.status, 400, `expected ${sha256} to be refused`);
      assert.equal(response.body.error, 'invalid_request');
    }
  });
});

test('an unsupported extraction may not carry text, and an extracted one must', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const fake = await upload(base, { extraction_status: 'unsupported', text: '看起来像正文' });
    assert.equal(fake.status, 422);
    assert.equal(fake.body.error, 'document_rejected');

    const empty = await upload(base, { extraction_status: 'extracted', text: '' });
    assert.equal(empty.status, 422);

    const honest = await upload(base, {
      extraction_status: 'unsupported',
      text: '',
      media_type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    });
    assert.equal(honest.status, 201);
    assert.equal(honest.body.extraction_status, 'unsupported');
    assert.equal(honest.body.text_chars, 0);
  });
});

test('a filename that is a path is refused', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    for (const filename of ['../../etc/passwd', 'a/b.md', 'a\\b.md', '', '   ']) {
      const response = await upload(base, { filename });
      assert.equal(response.status, 400, `expected ${filename} to be refused`);
    }
  });
});

test('a blank media type is refused', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await upload(base, { media_type: '  ' });
    assert.equal(response.status, 400);
  });
});

// ===== conditional delete =====

test('a delete is conditional on If-Match and bumps the row out of the list', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await upload(base);
    const id = created.body.id;

    const noHeader = await call(base, 'DELETE', `/internal/courses/course-1/materials/${id}`);
    assert.equal(noHeader.status, 400);

    const stale = await call(base, 'DELETE', `/internal/courses/course-1/materials/${id}`, {
      headers: headers({ extra: { 'if-match': '9' } }),
    });
    assert.equal(stale.status, 412);

    const deleted = await call(base, 'DELETE', `/internal/courses/course-1/materials/${id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    assert.equal(deleted.status, 200);
    assert.equal(deleted.body.deleted, true);

    const listed = await call(base, 'GET', '/internal/courses/course-1/materials');
    assert.equal(listed.body.items.length, 0);

    const fetched = await call(base, 'GET', `/internal/courses/course-1/materials/${id}`);
    assert.equal(fetched.status, 404);
  });
});

test('a deleted material can be re-uploaded as a new one', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await upload(base);
    await call(base, 'DELETE', `/internal/courses/course-1/materials/${created.body.id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    const again = await upload(base);
    assert.equal(again.status, 201);
    assert.notEqual(again.body.id, created.body.id);
    assert.equal(again.body.deduplicated, false);

    const listed = await call(base, 'GET', '/internal/courses/course-1/materials');
    assert.equal(listed.body.items.length, 1);
  });
});

// ===== references =====

test('resolve returns authorized references in request order and reports the rest', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const first = await upload(base, { sha256: DIGEST, filename: '甲.md' });
    const second = await upload(base, { sha256: OTHER_DIGEST, filename: '乙.md' });

    const resolved = await call(base, 'POST', '/internal/courses/course-1/materials/resolve', {
      body: { material_ids: [second.body.id, 'mt_missing', first.body.id] },
    });
    assert.equal(resolved.status, 200);
    assert.deepEqual(
      resolved.body.resolved.map((item) => item.id),
      [second.body.id, first.body.id],
    );
    assert.deepEqual(resolved.body.unresolved, ['mt_missing']);
    assert.equal(resolved.body.resolved[0].filename, '乙.md');
    assert.equal(resolved.body.resolved[0].text, undefined);
  });
});

test('resolve collapses duplicates and preserves the first position', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const first = await upload(base, { sha256: DIGEST });
    const second = await upload(base, { sha256: OTHER_DIGEST });
    const resolved = await call(base, 'POST', '/internal/courses/course-1/materials/resolve', {
      body: { material_ids: [first.body.id, second.body.id, first.body.id] },
    });
    assert.deepEqual(
      resolved.body.resolved.map((item) => item.id),
      [first.body.id, second.body.id],
    );
    assert.deepEqual(resolved.body.unresolved, []);
  });
});

test('resolve refuses a blank id, a non-list and an over-long list', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const blank = await call(base, 'POST', '/internal/courses/course-1/materials/resolve', {
      body: { material_ids: ['  '] },
    });
    assert.equal(blank.status, 400);

    const notAList = await call(base, 'POST', '/internal/courses/course-1/materials/resolve', {
      body: { material_ids: 'mt_1' },
    });
    assert.equal(notAList.status, 400);

    const tooMany = await call(base, 'POST', '/internal/courses/course-1/materials/resolve', {
      body: { material_ids: Array.from({ length: MAX_REFERENCE_COUNT + 1 }, (_, index) => `mt_${index}`) },
    });
    assert.equal(tooMany.status, 400);
  });
});

test('a deleted material stops resolving', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await upload(base);
    await call(base, 'DELETE', `/internal/courses/course-1/materials/${created.body.id}`, {
      headers: headers({ extra: { 'if-match': '1' } }),
    });
    const resolved = await call(base, 'POST', '/internal/courses/course-1/materials/resolve', {
      body: { material_ids: [created.body.id] },
    });
    assert.deepEqual(resolved.body.resolved, []);
    assert.deepEqual(resolved.body.unresolved, [created.body.id]);
  });
});

// ===== misc =====

test('an unknown material id is a plain 404 without an existence oracle', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await upload(base, { sub: 'user-2' });

    const missing = await call(base, 'GET', '/internal/courses/course-1/materials/mt_nope');
    assert.equal(missing.status, 404);
    assert.equal(missing.body.error, 'not_found');

    // The real property: "belongs to someone else" and "never existed" are the
    // same answer, byte for byte. A message difference would be an oracle.
    const foreign = await call(base, 'GET', `/internal/courses/course-1/materials/${created.body.id}`);
    assert.equal(foreign.status, 404);
    assert.deepEqual(foreign.body, missing.body);
  });
});

test('the material capability is advertised exactly once', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await fetch(`${base}/internal/health/ready`, {
      headers: headers({ scopes: ['service:status'] }),
    });
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.capabilities.filter((item) => item === 'material').length, 1);
  });
});

test('a missing read scope is forbidden and a missing write scope cannot create', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const noRead = await call(base, 'GET', '/internal/courses/course-1/materials', {
      headers: headers({ scopes: ['material:write'] }),
    });
    assert.equal(noRead.status, 403);

    const noWrite = await call(base, 'POST', '/internal/courses/course-1/materials', {
      body: {
        filename: 'x.md',
        media_type: 'text/markdown',
        byte_size: 1,
        sha256: DIGEST,
        extraction_status: 'extracted',
        text: 'x',
      },
      headers: headers({ scopes: ['material:read'], extra: { 'idempotency-key': nextKey('material') } }),
    });
    assert.equal(noWrite.status, 403);
  });
});

test('the material table remains migration 4 and the schema version tracks later additions', () => {
  assert.equal(SCHEMA_VERSION, MIGRATIONS.at(-1).version);
  assert.equal(MIGRATIONS.find((migration) => migration.name === 'materials')?.version, 4);
  const database = new ServiceDatabase(':memory:');
  const row = database.raw
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'materials'")
    .get();
  assert.equal(row?.name, 'materials');
  database.close();
});

test('the material byte cap sits under the transport cap so neither hides the other', () => {
  // Same ordering rule the DSL document cap follows: if the transport answered
  // first, `byte_size must be at most ...` would be documentation rather than
  // behaviour and the named 422 could never be observed.
  assert.ok(MAX_MATERIAL_BYTES < MAX_REQUEST_BODY_BYTES);
  assert.ok(MAX_MATERIAL_BYTES + MAX_MATERIAL_TEXT_BYTES < MAX_REQUEST_BODY_BYTES);
});
