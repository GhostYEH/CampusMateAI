import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { upsertEnv } from './magicclass-local.mjs';

test('upsertEnv fills blank local secrets without duplicating the key', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'campusmate-magicclass-env-'));
  const file = path.join(root, '.env');
  await writeFile(file, 'MAGICCLASS_INTERNAL_SECRET=\nMAGICCLASS_SERVICE_URL=http://127.0.0.1:4010\n', 'utf8');

  const changed = upsertEnv(
    file,
    [['MAGICCLASS_INTERNAL_SECRET', 'local-secret']],
    'test',
  );

  assert.deepEqual(changed, ['MAGICCLASS_INTERNAL_SECRET']);
  const contents = await readFile(file, 'utf8');
  assert.equal((contents.match(/^MAGICCLASS_INTERNAL_SECRET=/gm) || []).length, 1);
  assert.match(contents, /^MAGICCLASS_INTERNAL_SECRET=local-secret$/m);
  assert.match(contents, /^MAGICCLASS_SERVICE_URL=http:\/\/127\.0\.0\.1:4010$/m);
});
