import assert from 'node:assert/strict';
import { isAbsolute, join } from 'node:path';
import test from 'node:test';

import { ConfigError, loadConfig, resolveDatabasePath, SERVICE_ROOT } from '../src/config.ts';

const BASE_ENV = {
  OPENMAIC_HOST: '127.0.0.1',
  OPENMAIC_PORT: '4010',
  OPENMAIC_DATABASE_URL: './data/openmaic-service.db',
  OPENMAIC_INTERNAL_SECRET: 'secret',
};

test('refuses to start without an internal secret', () => {
  assert.throws(
    () => loadConfig({ ...BASE_ENV, OPENMAIC_INTERNAL_SECRET: '' }),
    (error) => error instanceof ConfigError && /OPENMAIC_INTERNAL_SECRET is required/.test(error.message),
  );
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_INTERNAL_SECRET: '   ' }), ConfigError);
});

test('refuses to start without a database location', () => {
  assert.throws(
    () => loadConfig({ ...BASE_ENV, OPENMAIC_DATABASE_URL: '' }),
    (error) => error instanceof ConfigError && /OPENMAIC_DATABASE_URL is required/.test(error.message),
  );
});

test('rejects a database URL that is not a local file', () => {
  for (const value of ['postgres://user:pw@host:5432/db', 'mysql://host/db', 'https://example.invalid/db']) {
    assert.throws(() => resolveDatabasePath(value), ConfigError, `expected ${value} to be rejected`);
  }
});

test('resolves a relative database path against the service root, never the cwd', () => {
  const resolved = resolveDatabasePath('./data/openmaic-service.db');
  assert.ok(isAbsolute(resolved));
  assert.equal(resolved, join(SERVICE_ROOT, 'data', 'openmaic-service.db'));
});

test('accepts the sqlite and file URL prefixes', () => {
  assert.equal(resolveDatabasePath('sqlite:./data/app.db'), join(SERVICE_ROOT, 'data', 'app.db'));
  assert.equal(resolveDatabasePath('file:./data/app.db'), join(SERVICE_ROOT, 'data', 'app.db'));
  assert.equal(resolveDatabasePath('file://./data/app.db'), join(SERVICE_ROOT, 'data', 'app.db'));
});

test('treats a single-letter prefix as a drive, not a URL scheme', () => {
  // `C:\...` must not be mistaken for a `c:` scheme, which previously made every
  // absolute Windows database path fail to start the service.
  const absolute = resolveDatabasePath('C:\\openmaic\\service.db');
  assert.ok(isAbsolute(absolute));
  assert.match(absolute, /service\.db$/);
});

test('defaults host and port without inventing a database', () => {
  const config = loadConfig({ OPENMAIC_INTERNAL_SECRET: 'secret', OPENMAIC_DATABASE_URL: ':memory:' });
  assert.equal(config.host, '127.0.0.1');
  assert.equal(config.port, 4010);
  assert.equal(config.databasePath, ':memory:');
});

test('rejects an out-of-range port', () => {
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_PORT: '0' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_PORT: '70000' }), ConfigError);
  assert.throws(() => loadConfig({ ...BASE_ENV, OPENMAIC_PORT: 'abc' }), ConfigError);
});

test('keeps the documented .env.example in step with the loader', async () => {
  const { readFileSync } = await import('node:fs');
  const example = readFileSync(join(SERVICE_ROOT, '.env.example'), 'utf8');
  const entries = Object.fromEntries(
    example
      .split('\n')
      .filter((line) => line.includes('=') && !line.trim().startsWith('#'))
      .map((line) => [line.slice(0, line.indexOf('=')).trim(), line.slice(line.indexOf('=') + 1).trim()]),
  );
  // The template must ship a working database location; an empty value is what
  // previously made readiness a permanent 503.
  assert.notEqual(entries.OPENMAIC_DATABASE_URL, '');
  // The secret stays empty on purpose: it is injected, never committed.
  assert.equal(entries.OPENMAIC_INTERNAL_SECRET, '');

  const config = loadConfig({
    OPENMAIC_HOST: entries.OPENMAIC_HOST,
    OPENMAIC_PORT: entries.OPENMAIC_PORT,
    OPENMAIC_DATABASE_URL: entries.OPENMAIC_DATABASE_URL,
    OPENMAIC_INTERNAL_SECRET: 'injected',
  });
  assert.ok(isAbsolute(config.databasePath));
});
