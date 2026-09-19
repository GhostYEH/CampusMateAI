import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { MIGRATIONS, SCHEMA_VERSION } from '../src/db/migrations.ts';
import { SqliteReplayStore } from '../src/db/replayStore.ts';

function record(overrides = {}) {
  return {
    jti: 'jti-1',
    issuer: 'campusmate-backend',
    audience: 'openmaic-service',
    subject: 'user-1',
    courseId: 'course-1',
    scopes: ['workspace:read'],
    issuedAt: 100,
    expiresAt: 160,
    consumedAt: 100,
    ...overrides,
  };
}

test('applies every migration exactly once and records them', () => {
  const directory = mkdtempSync(join(tmpdir(), 'openmaic-db-'));
  const path = join(directory, 'service.db');

  const first = new ServiceDatabase(path);
  const applied = first.raw.prepare('SELECT version, name FROM schema_migrations ORDER BY version').all();
  assert.equal(applied.length, MIGRATIONS.length);
  assert.equal(Number(applied.at(-1).version), SCHEMA_VERSION);
  first.close();

  // Re-opening must not re-run migrations, which is what keeps `CREATE TABLE`
  // statements free of defensive `IF NOT EXISTS` clauses.
  const second = new ServiceDatabase(path);
  const reopened = second.raw.prepare('SELECT count(*) AS total FROM schema_migrations').get();
  assert.equal(Number(reopened.total), MIGRATIONS.length);
  second.close();
});

test('migration versions are unique and ascending', () => {
  const versions = MIGRATIONS.map((migration) => migration.version);
  assert.deepEqual(versions, [...versions].sort((left, right) => left - right));
  assert.equal(new Set(versions).size, versions.length);
});

test('rolls the whole transaction back when the work throws', () => {
  const database = new ServiceDatabase(':memory:');
  const replayStore = new SqliteReplayStore(database);

  assert.throws(() => {
    database.transaction(() => {
      replayStore.consume(record());
      throw new Error('write failed');
    });
  }, /write failed/);

  const total = database.raw.prepare('SELECT count(*) AS total FROM consumed_service_assertions').get();
  assert.equal(Number(total.total), 0);
  database.close();
});

test('re-entrant rollback undoes the inner write too', () => {
  const database = new ServiceDatabase(':memory:');
  const replayStore = new SqliteReplayStore(database);

  try {
    database.transaction(() => {
      database.transaction(() => replayStore.consume(record({ jti: 'inner' })));
      throw new Error('outer failed');
    });
  } catch {
    // expected
  }

  const total = database.raw.prepare('SELECT count(*) AS total FROM consumed_service_assertions').get();
  assert.equal(Number(total.total), 0);
  database.close();
});

test('rejects a duplicate jti inside the same transaction', () => {
  const database = new ServiceDatabase(':memory:');
  const replayStore = new SqliteReplayStore(database);
  database.transaction(() => {
    replayStore.consume(record({ jti: 'same' }));
    assert.throws(() => replayStore.consume(record({ jti: 'same' })), /replay/i);
  });
  database.close();
});

test('prunes assertion records once their window closes', () => {
  const database = new ServiceDatabase(':memory:');
  const replayStore = new SqliteReplayStore(database);

  replayStore.consume(record({ jti: 'old', expiresAt: 100 }));
  // Consuming the next assertion opportunistically drops records whose window
  // has already closed, so the expired row is gone before an explicit prune.
  replayStore.consume(record({ jti: 'live', expiresAt: 500 }));
  assert.deepEqual(
    database.raw.prepare('SELECT jti FROM consumed_service_assertions ORDER BY jti').all().map((row) => row.jti),
    ['live'],
  );

  // Once the surviving window closes, the explicit prune removes it.
  assert.equal(replayStore.pruneExpired(500), 1);
  assert.deepEqual(database.raw.prepare('SELECT jti FROM consumed_service_assertions').all(), []);
  database.close();
});

test('stores the assertion audit summary without the assertion itself', () => {
  const database = new ServiceDatabase(':memory:');
  const replayStore = new SqliteReplayStore(database);
  replayStore.consume(record());

  const row = database.raw.prepare('SELECT * FROM consumed_service_assertions').get();
  assert.equal(row.subject, 'user-1');
  assert.equal(row.course_id, 'course-1');
  assert.deepEqual(JSON.parse(row.scopes), ['workspace:read']);
  assert.equal(Object.values(row).some((value) => typeof value === 'string' && value.includes('eyJ')), false);
  database.close();
});
