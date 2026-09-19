import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { createProviderRoutes } from '../src/provider/routes.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

test('provider status exposes only boolean capabilities and never configuration values', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: createProviderRoutes({ database, providers: {
    llm: true, webSearch: false, image: true, video: false, tts: false, render: true, external3d: false,
  } }) });
  await withServer(server, async (base) => {
    const response = await fetch(`${base}/internal/settings/providers`, { headers: { 'x-campusmate-service-assertion': mintAssertion({ scopes: ['service:status'] }) } });
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.deepEqual(body, { llm: true, web_search: false, image: true, video: false, tts: false, render: true, external_3d: false });
    assert.equal(JSON.stringify(body).includes('key'), false);
    assert.equal(JSON.stringify(body).includes('url'), false);
  });
});
