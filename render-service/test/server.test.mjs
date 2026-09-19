import assert from 'node:assert/strict';
import test from 'node:test';
import { createRenderServer, MAX_RENDER_BODY_BYTES } from '../src/server.ts';
import { loadConfig, RenderConfigError } from '../src/config.ts';

async function withServer(server, run) {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  try { return await run(`http://127.0.0.1:${port}`); } finally { await new Promise((resolve) => server.close(resolve)); }
}

test('render service is loopback-friendly, token protected, and returns only mp4 bytes', async () => {
  const server = createRenderServer({ token: 'render-secret', renderer: async () => Buffer.from('fake-mp4') });
  await withServer(server, async (base) => {
    assert.equal((await fetch(`${base}/internal/health`)).status, 200);
    const denied = await fetch(`${base}/internal/render`, { method: 'POST', body: '{}' });
    assert.equal(denied.status, 401);
    const response = await fetch(`${base}/internal/render`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-render-service-token': 'render-secret' },
      body: JSON.stringify({ document: { stage: { name: '函数极限' }, scenes: [{ title: '定义' }] } }),
    });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('content-type'), 'video/mp4');
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), Buffer.from('fake-mp4'));
  });
});

test('render service refuses oversized or structurally unsafe stage input', async () => {
  const server = createRenderServer({ token: 'render-secret', renderer: async () => Buffer.from('fake') });
  await withServer(server, async (base) => {
    const oversized = await fetch(`${base}/internal/render`, {
      method: 'POST', headers: { 'x-render-service-token': 'render-secret' }, body: 'x'.repeat(MAX_RENDER_BODY_BYTES + 1),
    });
    assert.equal(oversized.status, 413);
    const invalid = await fetch(`${base}/internal/render`, {
      method: 'POST', headers: { 'x-render-service-token': 'render-secret', 'content-type': 'application/json' }, body: JSON.stringify({ document: { scenes: [] } }),
    });
    assert.equal(invalid.status, 422);
  });
});

test('render config requires a private token and bounds the process', () => {
  assert.throws(() => loadConfig({}), RenderConfigError);
  const config = loadConfig({ RENDER_SERVICE_TOKEN: 'secret', RENDER_SERVICE_PORT: '9010', RENDER_SERVICE_HOST: '127.0.0.1', FFMPEG_PATH: 'ffmpeg' });
  assert.deepEqual(config, { host: '127.0.0.1', port: 9010, token: 'secret', ffmpegPath: 'ffmpeg', timeoutMs: 120000 });
});
