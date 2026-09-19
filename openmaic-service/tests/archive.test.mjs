/**
 * `.maic.zip` export + import tests.
 *
 * A container reader is where a serializer turns into an attack surface, so the
 * hostile fixtures here are built by a **separate minimal zip writer defined in
 * this file** rather than by `writeZip`. Reusing the code under test to craft its
 * own malformed input would only prove the two agree, not that either is right.
 *
 * The rules being pinned:
 *
 * - a name that could become a path outside the archive is refused;
 * - a declared size or a CRC that does not match the data is refused;
 * - encryption, Zip64 and unknown compression methods are refused **by name**,
 *   never mis-parsed into plausible output;
 * - the bomb bounds are applied from the directory **before** inflating, and the
 *   declared size is re-checked against what actually came out;
 * - an imported stage still goes through `prepareStage`, so an archive is not a
 *   way to write a document the editor would refuse;
 * - nothing inside an archive decides who owns the import.
 */
import assert from 'node:assert/strict';
import { deflateRawSync } from 'node:zlib';
import test from 'node:test';

import { createArchiveRoutes } from '../src/archive/routes.ts';
import { MAX_ARCHIVE_BYTES, MANIFEST_PATH, stagePathFor, MAIC_FORMAT, MAIC_FORMAT_VERSION } from '../src/archive/manifest.ts';
import { readArchive, decodeArchivePayload } from '../src/archive/import.ts';
import { ZIP_LIMITS, crc32, isSafeEntryName, readZip, writeZip } from '../src/archive/zip.ts';
import { DSL_LIMITS } from '../src/dsl/limits.ts';
import { DSL_VERSION } from '../src/dsl/version.ts';
import { MAX_REQUEST_BODY_BYTES } from '../src/server.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { createWorkspaceRoutes } from '../src/workspace/routes.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const ALL_SCOPES = [
  'workspace:read',
  'workspace:write',
  'archive:read',
  'archive:write',
];

// ===== an independent minimal zip writer, for hostile fixtures =====

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  return table;
})();

function crc32Of(buffer) {
  let crc = 0xffffffff;
  for (let index = 0; index < buffer.length; index += 1) {
    crc = CRC_TABLE[(crc ^ buffer[index]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/**
 * Build raw zip bytes with full control over every field an attacker controls.
 * Deliberately independent of `src/archive/zip.ts`.
 */
function hostileZip(entries, { entryCountOverride, zip64Eocd = false } = {}) {
  const locals = [];
  const centrals = [];
  let offset = 0;

  for (const entry of entries) {
    const name = Buffer.from(entry.name, 'utf8');
    const data = Buffer.isBuffer(entry.data) ? entry.data : Buffer.from(entry.data ?? '', 'utf8');
    const method = entry.method ?? 8;
    const flag = entry.flag ?? 0;
    const payload = method === 8 ? deflateRawSync(data) : data;
    const crc = entry.crc ?? crc32Of(data);
    const declared = entry.declaredSize ?? data.length;
    const externalAttrs = entry.externalAttrs ?? (0o100644 << 16) >>> 0;
    const madeBy = entry.madeBy ?? (3 << 8) | 20;

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(flag, 6);
    local.writeUInt16LE(method, 8);
    local.writeUInt16LE(0, 10);
    local.writeUInt16LE(0, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(payload.length, 18);
    local.writeUInt32LE(declared, 22);
    local.writeUInt16LE(name.length, 26);
    local.writeUInt16LE(0, 28);
    locals.push(local, name, payload);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(madeBy, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(flag, 8);
    central.writeUInt16LE(method, 10);
    central.writeUInt16LE(0, 12);
    central.writeUInt16LE(0, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(payload.length, 20);
    central.writeUInt32LE(declared, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt16LE(0, 30);
    central.writeUInt16LE(0, 32);
    central.writeUInt16LE(0, 34);
    central.writeUInt16LE(0, 36);
    central.writeUInt32LE(externalAttrs, 38);
    central.writeUInt32LE(offset, 42);
    centrals.push(central, name);

    offset += 30 + name.length + payload.length;
  }

  const centralBytes = Buffer.concat(centrals);
  const count = entryCountOverride ?? entries.length;
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(zip64Eocd ? 0xffff : count, 8);
  eocd.writeUInt16LE(zip64Eocd ? 0xffff : count, 10);
  eocd.writeUInt32LE(centralBytes.length, 12);
  eocd.writeUInt32LE(offset, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([...locals, centralBytes, eocd]);
}

// ===== fixtures =====

function stageDocument(title = '第一章') {
  return {
    stage: { id: 'stage_doc', name: title, createdAt: 1, updatedAt: 1 },
    scenes: [
      {
        id: 'sc_1',
        stageId: 'stage_doc',
        title: '开场',
        order: 1,
        type: 'slide',
        content: { type: 'slide', canvas: {} },
      },
    ],
  };
}

function archiveBytes({ title = '第一章', document = stageDocument(title), manifestOverrides = {}, extraEntries = [] } = {}) {
  const stagePath = stagePathFor('stg_exported');
  const manifest = {
    format: MAIC_FORMAT,
    format_version: MAIC_FORMAT_VERSION,
    exported_at: '2026-01-01T00:00:00.000Z',
    dsl_version: DSL_VERSION,
    source: { workspace_name: '期末复习' },
    stage: { path: stagePath, title, dsl_version: DSL_VERSION },
    ...manifestOverrides,
  };
  return writeZip(
    [
      { name: MANIFEST_PATH, data: Buffer.from(JSON.stringify(manifest), 'utf8') },
      { name: stagePath, data: Buffer.from(JSON.stringify(document), 'utf8') },
      ...extraEntries,
    ],
    { modifiedAt: new Date('2026-01-01T00:00:00.000Z') },
  );
}

// ===== harness =====

function harness() {
  const database = new ServiceDatabase(':memory:');
  const routes = [...createWorkspaceRoutes({ database }), ...createArchiveRoutes({ database })];
  return { database, ...createHarness({ database, routes }) };
}

function headers({ sub = 'user-1', courseId = 'course-1', scopes = ALL_SCOPES, extra = {} } = {}) {
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

function createWorkspace(base, { name = '期末复习', sub = 'user-1' } = {}) {
  return call(base, 'POST', '/internal/courses/course-1/workspaces', {
    body: { name, description: '' },
    headers: headers({ sub, extra: { 'idempotency-key': nextKey('ws') } }),
  });
}

function createStage(base, workspaceId, { title = '第一章', document, sub = 'user-1' } = {}) {
  return call(base, 'POST', `/internal/courses/course-1/workspaces/${workspaceId}/stages`, {
    body: document === undefined ? { title } : { title, document },
    headers: headers({ sub, extra: { 'idempotency-key': nextKey('stage') } }),
  });
}

function importArchive(base, workspaceId, archive, { sub = 'user-1', courseId = 'course-1', key } = {}) {
  return call(base, 'POST', `/internal/courses/${courseId}/workspaces/${workspaceId}/import`, {
    body: { archive: archive.toString('base64') },
    headers: headers({ sub, courseId, extra: { 'idempotency-key': key ?? nextKey('import') } }),
  });
}

// ===== zip: round trip and determinism =====

test('an archive written here reads back byte for byte', () => {
  const entries = [
    { name: MANIFEST_PATH, data: Buffer.from('{"a":1}', 'utf8') },
    { name: 'stages/stg_1.json', data: Buffer.from('变长文本'.repeat(50), 'utf8') },
  ];
  const archive = writeZip(entries, { modifiedAt: new Date('2026-01-01T00:00:00.000Z') });
  const read = readZip(archive);
  assert.deepEqual(read.map((entry) => entry.name), entries.map((entry) => entry.name));
  for (const [index, entry] of entries.entries()) {
    assert.equal(read[index].data.toString('utf8'), entry.data.toString('utf8'));
  }
});

test('the same entries and timestamp produce the same bytes', () => {
  const entries = [{ name: 'stages/stg_1.json', data: Buffer.from('内容', 'utf8') }];
  const when = new Date('2026-02-03T04:05:06.000Z');
  assert.deepEqual(writeZip(entries, { modifiedAt: when }), writeZip(entries, { modifiedAt: when }));
});

test('an incompressible entry is stored rather than grown', () => {
  const random = Buffer.alloc(4096);
  for (let index = 0; index < random.length; index += 1) random[index] = (index * 7 + (index % 13)) & 0xff;
  const archive = writeZip([{ name: 'blob.bin', data: random }], { modifiedAt: new Date('2026-01-01T00:00:00.000Z') });
  assert.equal(readZip(archive)[0].data.length, random.length);
  assert.ok(archive.length <= random.length + 200, 'stored entry should not be inflated by deflate overhead');
});

test('crc32 matches the reference value for a known input', () => {
  assert.equal(crc32(Buffer.from('123456789', 'ascii')), 0xcbf43926);
});

// ===== zip: name policy =====

test('a name that could become a path outside the archive is not safe', () => {
  for (const name of [
    '',
    '/etc/passwd',
    'C:/Windows/system32',
    'a\\b.json',
    '../escape.json',
    'a/../../escape.json',
    './a.json',
    'a/./b.json',
    'a//b.json',
    'stages/',
    'bad\u0000name.json',
    'x'.repeat(ZIP_LIMITS.maxNameBytes + 1),
  ]) {
    assert.equal(isSafeEntryName(name), false, `expected ${JSON.stringify(name)} to be unsafe`);
  }
  assert.equal(isSafeEntryName('stages/stg_1.json'), true);
  assert.equal(isSafeEntryName('manifest.json'), true);
});

test('a hostile name is refused when reading, not normalised', () => {
  const archive = hostileZip([{ name: '../../escape.json', data: 'x' }]);
  assert.throws(() => readZip(archive), /not safe/);
});

// ===== zip: integrity and unsupported features =====

test('a mismatched CRC is refused', () => {
  const archive = hostileZip([{ name: 'a.json', data: 'hello', crc: 0xdeadbeef }]);
  assert.throws(() => readZip(archive), /integrity check/);
});

test('a declared size that disagrees with the data is refused', () => {
  const archive = hostileZip([{ name: 'a.json', data: 'hello', declaredSize: 99 }]);
  assert.throws(() => readZip(archive), /size does not match/);
});

test('an encrypted entry is refused by name', () => {
  const archive = hostileZip([{ name: 'a.json', data: 'hello', flag: 0x0001 }]);
  assert.throws(() => readZip(archive), /encrypted/);
});

test('an unsupported compression method is refused instead of mis-parsed', () => {
  const archive = hostileZip([{ name: 'a.json', data: 'hello', method: 12 }]);
  assert.throws(() => readZip(archive), /unsupported compression method/);
});

test('a zip64 archive is refused rather than half-read', () => {
  const archive = hostileZip([{ name: 'a.json', data: 'hello' }], { zip64Eocd: true });
  assert.throws(() => readZip(archive), /zip64/);
});

test('a symbolic link entry is refused', () => {
  const archive = hostileZip([{ name: 'link.json', data: '/etc/passwd', externalAttrs: 0xa1ff0000 }]);
  assert.throws(() => readZip(archive), /symbolic link/);
});

test('a duplicate entry name is refused', () => {
  const archive = hostileZip([
    { name: 'a.json', data: 'one' },
    { name: 'a.json', data: 'two' },
  ]);
  assert.throws(() => readZip(archive), /duplicate entry/);
});

test('bytes that are not a zip at all are an invalid request, not a rejection', () => {
  assert.throws(() => readZip(Buffer.from('not a zip')), (error) => error.code === 'invalid_request');
  assert.throws(() => readZip(Buffer.alloc(4)), (error) => error.code === 'invalid_request');
});

// ===== zip: bomb bounds =====

test('an entry whose declared size exceeds the per-entry cap is refused before inflating', () => {
  const archive = hostileZip([
    { name: 'big.json', data: 'x', declaredSize: ZIP_LIMITS.maxEntryBytes + 1 },
  ]);
  assert.throws(() => readZip(archive), /exceeds .* bytes/);
});

test('an archive whose declared total exceeds the total cap is refused', () => {
  // Three entries that each fit the per-entry cap but together breach the total:
  // the bound has to be enforced on the running sum, not per entry.
  const chunk = Buffer.alloc(ZIP_LIMITS.maxTotalBytes / 2 - 512);
  const archive = hostileZip(
    Array.from({ length: 3 }, (_, index) => ({
      name: `part-${index}.json`,
      data: chunk,
    })),
  );
  assert.throws(() => readZip(archive), /inflates beyond/);
});

test('too many entries are refused', () => {
  const archive = hostileZip(
    Array.from({ length: ZIP_LIMITS.maxEntries + 1 }, (_, index) => ({
      name: `part-${index}.json`,
      data: 'x',
    })),
  );
  assert.throws(() => readZip(archive), /more than .* entries/);
});

test('a real deflate bomb is stopped by the declared-size bound', () => {
  // 6 MiB of zeros compresses to a few KiB — a genuine bomb shape.
  const bomb = hostileZip([{ name: 'bomb.json', data: Buffer.alloc(6 * 1024 * 1024) }]);
  assert.ok(bomb.length < 64 * 1024, 'the fixture should be small on the wire');
  assert.throws(() => readZip(bomb), /exceeds .* bytes/);
});

// ===== manifest =====

test('a valid archive reports its manifest and document', () => {
  const read = readArchive(archiveBytes());
  assert.equal(read.manifest.format, MAIC_FORMAT);
  assert.equal(read.manifest.format_version, MAIC_FORMAT_VERSION);
  assert.equal(read.manifest.source.workspace_name, '期末复习');
  assert.equal(read.document.stage.name, '第一章');
});

test('a foreign format is refused', () => {
  assert.throws(() => readArchive(archiveBytes({ manifestOverrides: { format: 'other.thing' } })), /not a campusmate\.maic/);
});

test('a newer format_version is refused rather than partially read', () => {
  assert.throws(
    () => readArchive(archiveBytes({ manifestOverrides: { format_version: MAIC_FORMAT_VERSION + 1 } })),
    /newer than this build supports/,
  );
});

test('an archive without a manifest is refused', () => {
  const archive = writeZip([{ name: 'stages/stg_1.json', data: Buffer.from('{}', 'utf8') }], {
    modifiedAt: new Date('2026-01-01T00:00:00.000Z'),
  });
  assert.throws(() => readArchive(archive), /no manifest\.json/);
});

test('an archive missing the stage it declares is refused', () => {
  const stagePath = stagePathFor('stg_exported');
  const manifest = {
    format: MAIC_FORMAT,
    format_version: MAIC_FORMAT_VERSION,
    stage: { path: stagePath, title: 'x', dsl_version: DSL_VERSION },
  };
  const archive = writeZip([{ name: MANIFEST_PATH, data: Buffer.from(JSON.stringify(manifest), 'utf8') }], {
    modifiedAt: new Date('2026-01-01T00:00:00.000Z'),
  });
  assert.throws(() => readArchive(archive), /missing the stage it declares/);
});

test('an extra entry is refused, because this format version cannot represent it', () => {
  const archive = archiveBytes({
    extraEntries: [{ name: 'assets/extra.bin', data: Buffer.from('surprise', 'utf8') }],
  });
  assert.throws(() => readArchive(archive), /does not define/);
});

// ===== payload decoding =====

test('the base64 payload is validated strictly', () => {
  assert.throws(() => decodeArchivePayload(123), /base64 string/);
  assert.throws(() => decodeArchivePayload(''), /base64 string/);
  assert.throws(() => decodeArchivePayload('not base64!!'), /not valid base64/);
  assert.throws(() => decodeArchivePayload('abc'), /not valid base64/);
  assert.equal(decodeArchivePayload(Buffer.from('hi').toString('base64')).toString(), 'hi');
});

test('an oversize payload is refused before it is decoded', () => {
  const oversize = 'A'.repeat(Math.ceil(MAX_ARCHIVE_BYTES / 3) * 4 + 8);
  assert.throws(() => decodeArchivePayload(oversize), (error) => error.code === 'document_rejected');
});

test('the base64 form of the biggest legal archive still fits the transport cap', () => {
  // If it did not, the transport would answer first and the named archive limit
  // could never be observed — the same ordering rule the DSL and material caps
  // already follow.
  const encoded = Math.ceil(MAX_ARCHIVE_BYTES / 3) * 4;
  const envelope = Buffer.byteLength('{"archive":""}', 'utf8');
  assert.ok(encoded + envelope < MAX_REQUEST_BODY_BYTES, `${encoded + envelope} must be below ${MAX_REQUEST_BODY_BYTES}`);
});

test('an entry can hold a document up to the DSL document cap', () => {
  assert.ok(ZIP_LIMITS.maxEntryBytes >= DSL_LIMITS.maxDocumentBytes);
});

// ===== routes: round trip =====

test('a stage exports and imports back with the same document', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base, { name: '期末复习' });
    const stage = await createStage(base, workspace.body.id, { title: '第一章', document: stageDocument() });
    assert.equal(stage.status, 201);

    const exported = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${stage.body.id}/export`,
    );
    assert.equal(exported.status, 200);
    assert.equal(exported.body.format, MAIC_FORMAT);
    assert.equal(exported.body.stage_title, '第一章');
    assert.match(exported.body.filename, /\.maic\.zip$/);
    assert.equal(exported.body.sha256.length, 64);
    assert.equal(exported.body.byte_size, Buffer.from(exported.body.archive, 'base64').length);

    // Import into a *different* workspace: the archive's own workspace name must
    // not decide where the stage lands.
    const target = await createWorkspace(base, { name: '另一门课' });
    const imported = await importArchive(base, target.body.id, Buffer.from(exported.body.archive, 'base64'));
    assert.equal(imported.status, 201, JSON.stringify(imported.body));
    assert.equal(imported.body.stage.workspace_id, target.body.id);
    assert.equal(imported.body.stage.title, '第一章');
    assert.equal(imported.body.source_workspace_name, '期末复习');
    assert.equal(imported.body.migrated, false);

    const fetched = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${target.body.id}/stages/${imported.body.stage.id}`,
    );
    assert.equal(fetched.status, 200);
    assert.equal(fetched.body.document.scenes.length, 1);
    assert.equal(fetched.body.document.scenes[0].title, '开场');
    assert.equal(fetched.body.document.dslVersion, DSL_VERSION);
  });
});

test('importing twice with one idempotency key creates one stage', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const archive = archiveBytes();
    const key = 'import-replay';
    const first = await importArchive(base, workspace.body.id, archive, { key });
    const replay = await importArchive(base, workspace.body.id, archive, { key });
    assert.equal(replay.status, 201);
    assert.equal(replay.body.stage.id, first.body.stage.id);

    const listed = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`);
    assert.equal(listed.body.items.length, 1);
  });
});

test('an import without an idempotency key is refused', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const response = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/import`, {
      body: { archive: archiveBytes().toString('base64') },
    });
    assert.equal(response.status, 400);
    assert.equal(response.body.error, 'invalid_request');
  });
});

// ===== routes: a document the DSL would refuse cannot be imported =====

test('an archive carrying an invalid document is refused and creates nothing', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const broken = archiveBytes({ document: { stage: { id: 'x' }, scenes: [{ id: 's', type: 'nope' }] } });
    const response = await importArchive(base, workspace.body.id, broken);
    assert.equal(response.status, 422);
    assert.equal(response.body.error, 'document_rejected');

    const listed = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`);
    assert.equal(listed.body.items.length, 0, 'a rejected import must leave no stage behind');
  });
});

test('an empty stage imports as an empty stage, not as an error', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const archive = archiveBytes({ document: { stage: { id: 'e', name: '空', createdAt: 1, updatedAt: 1 }, scenes: [] } });
    const response = await importArchive(base, workspace.body.id, archive);
    assert.equal(response.status, 201);
    const fetched = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${response.body.stage.id}`,
    );
    assert.deepEqual(fetched.body.document.scenes, []);
  });
});

test('a blank title in the manifest falls back instead of creating an unnamed stage', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    // The *manifest* title is blank; the document itself stays valid, because a
    // blank stage name inside the document is a different (and correctly fatal)
    // problem — that one belongs to the DSL.
    const response = await importArchive(
      base,
      workspace.body.id,
      archiveBytes({ title: '   ', document: stageDocument('第一章') }),
    );
    assert.equal(response.status, 201, JSON.stringify(response.body));
    assert.ok(response.body.stage.title.trim().length > 0);
    assert.notEqual(response.body.stage.title, '   ');
  });
});

// ===== routes: ownership =====

test('another user cannot export the stage and cannot import into the workspace', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base, { sub: 'user-1' });
    const stage = await createStage(base, workspace.body.id, { sub: 'user-1' });

    const foreignExport = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${stage.body.id}/export`,
      { headers: headers({ sub: 'user-2' }) },
    );
    assert.equal(foreignExport.status, 404);
    assert.equal(foreignExport.body.error, 'not_found');

    const foreignImport = await importArchive(base, workspace.body.id, archiveBytes(), { sub: 'user-2' });
    assert.equal(foreignImport.status, 404);

    const listed = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`, {
      headers: headers({ sub: 'user-1' }),
    });
    assert.equal(listed.body.items.length, 1, 'the foreign import must not have created anything');
  });
});

test('a stage cannot be exported through another workspace id', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const first = await createWorkspace(base, { name: '甲' });
    const second = await createWorkspace(base, { name: '乙' });
    const stage = await createStage(base, first.body.id);
    const response = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${second.body.id}/stages/${stage.body.id}/export`,
    );
    assert.equal(response.status, 404);
  });
});

test('a stage cannot be exported through another course', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const stage = await createStage(base, workspace.body.id);
    const response = await call(
      base,
      'GET',
      `/internal/courses/course-9/workspaces/${workspace.body.id}/stages/${stage.body.id}/export`,
      { headers: headers({ courseId: 'course-9' }) },
    );
    assert.equal(response.status, 404);
  });
});

// ===== routes: scopes and capability =====

test('export needs archive:read and import needs archive:write', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const workspace = await createWorkspace(base);
    const stage = await createStage(base, workspace.body.id);
    const readOnly = ['archive:read', 'workspace:read', 'workspace:write'];
    const writeOnly = ['archive:write', 'workspace:read', 'workspace:write'];

    const noRead = await call(
      base,
      'GET',
      `/internal/courses/course-1/workspaces/${workspace.body.id}/stages/${stage.body.id}/export`,
      { headers: headers({ scopes: writeOnly }) },
    );
    assert.equal(noRead.status, 403);

    const noWrite = await call(base, 'POST', `/internal/courses/course-1/workspaces/${workspace.body.id}/import`, {
      body: { archive: archiveBytes().toString('base64') },
      headers: headers({ scopes: readOnly, extra: { 'idempotency-key': nextKey('import') } }),
    });
    assert.equal(noWrite.status, 403);

    const listed = await call(base, 'GET', `/internal/courses/course-1/workspaces/${workspace.body.id}/stages`);
    assert.equal(listed.body.items.length, 1, 'a forbidden import must create nothing');
  });
});

test('both archive capabilities are advertised exactly once', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const response = await fetch(`${base}/internal/health/ready`, {
      headers: headers({ scopes: ['service:status'] }),
    });
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.capabilities.filter((item) => item === 'export-maic').length, 1);
    assert.equal(payload.capabilities.filter((item) => item === 'import-maic').length, 1);
  });
});
