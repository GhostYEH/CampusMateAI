import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { createTtsRoutes } from '../src/tts/routes.ts';
import { createDiscussionRoutes } from '../src/discussion/routes.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

function headers(scopes) {
  return { 'x-campusmate-service-assertion': mintAssertion({ scopes }), 'content-type': 'application/json' };
}

async function call(base, method, path, body, scopes) {
  const response = await fetch(`${base}${path}`, { method, headers: headers(scopes), body: JSON.stringify(body) });
  return { status: response.status, body: await response.json() };
}

test('tts reports an explicit provider degradation and never fabricates audio', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: createTtsRoutes({ database, available: false }) });
  await withServer(server, async (base) => {
    const result = await call(base, 'POST', '/internal/courses/course-1/tts', { text: '你好' }, ['tts:write']);
    assert.equal(result.status, 503);
    assert.equal(result.body.error, 'provider_unavailable');
    assert.equal(result.body.audio_base64, undefined);
  });
});

test('multi-agent discussion rejects empty input and returns a bounded degraded contract', async () => {
  const database = new ServiceDatabase(':memory:');
  const { server } = createHarness({ database, routes: createDiscussionRoutes({ database, available: false }) });
  await withServer(server, async (base) => {
    const empty = await call(base, 'POST', '/internal/courses/course-1/discussion', { prompt: '' }, ['multi-agent:write']);
    assert.equal(empty.status, 400);
    const unavailable = await call(base, 'POST', '/internal/courses/course-1/discussion', { prompt: '讨论函数极限' }, ['multi-agent:write']);
    assert.equal(unavailable.status, 503);
    assert.equal(unavailable.body.error, 'provider_unavailable');
    assert.equal(unavailable.body.messages, undefined);
  });
});
