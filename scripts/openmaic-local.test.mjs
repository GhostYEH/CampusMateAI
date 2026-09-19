import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { upsertEnv } from './openmaic-local.mjs';

test('upsertEnv fills blank local secrets without duplicating the key', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'campusmate-openmaic-env-'));
  const file = path.join(root, '.env');
  await writeFile(file, 'OPENMAIC_INTERNAL_SECRET=\nOPENMAIC_SERVICE_URL=http://127.0.0.1:4010\n', 'utf8');

  const changed = upsertEnv(
    file,
    [['OPENMAIC_INTERNAL_SECRET', 'local-secret']],
    'test',
  );

  assert.deepEqual(changed, ['OPENMAIC_INTERNAL_SECRET']);
  const contents = await readFile(file, 'utf8');
  assert.equal((contents.match(/^OPENMAIC_INTERNAL_SECRET=/gm) || []).length, 1);
  assert.match(contents, /^OPENMAIC_INTERNAL_SECRET=local-secret$/m);
  assert.match(contents, /^OPENMAIC_SERVICE_URL=http:\/\/127\.0\.0\.1:4010$/m);
});
