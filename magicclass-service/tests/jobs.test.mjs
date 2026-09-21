import assert from 'node:assert/strict';
import test from 'node:test';

import { ServiceDatabase } from '../src/db/database.ts';
import { createJobRoutes } from '../src/jobs/routes.ts';
import { createHarness, mintAssertion, withServer } from './helpers.mjs';

const JOB_SCOPES = ['job:read', 'job:write', 'job:cancel'];

function harness() {
  const database = new ServiceDatabase(':memory:');
  return { database, ...createHarness({ database, routes: createJobRoutes({ database }) }) };
}

function headers({ sub = 'user-1', courseId = 'course-1', scopes = JOB_SCOPES, extra = {} } = {}) {
  return {
    'x-campusmate-service-assertion': mintAssertion({ sub, courseId, scopes }),
    'content-type': 'application/json',
    ...extra,
  };
}

async function call(base, method, path, { body, ...options } = {}) {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: options.headers ?? headers(),
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : null };
}

test('creates one owned job for an idempotent request and reports progress', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const first = await call(base, 'POST', '/internal/courses/course-1/jobs', {
      body: { kind: 'generation', mode: 'slide', input: { prompt: '函数极限' } },
      headers: headers({ extra: { 'idempotency-key': 'generate-1' } }),
    });
    assert.equal(first.status, 201);
    assert.match(first.body.id, /^job_/);
    assert.equal(first.body.status, 'queued');
    assert.equal(first.body.progress, 0);

    const replay = await call(base, 'POST', '/internal/courses/course-1/jobs', {
      body: { kind: 'generation', mode: 'slide', input: { prompt: '函数极限' } },
      headers: headers({ extra: { 'idempotency-key': 'generate-1' } }),
    });
    assert.deepEqual(replay, first);

    const current = await call(base, 'GET', `/internal/courses/course-1/jobs/${first.body.id}`);
    assert.equal(current.status, 200);
    assert.equal(current.body.id, first.body.id);
    assert.equal(current.body.progress, 0);
    assert.equal(current.body.secret, undefined);
  });
});

test('job state transitions support cancel and retry without exposing provider details', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await call(base, 'POST', '/internal/courses/course-1/jobs', {
      body: { kind: 'export', format: 'markdown', stage_id: 'stage-1' },
      headers: headers({ extra: { 'idempotency-key': 'export-1' } }),
    });
    const cancel = await call(base, 'POST', `/internal/courses/course-1/jobs/${created.body.id}/cancel`, {
      headers: headers(),
    });
    assert.equal(cancel.status, 200);
    assert.equal(cancel.body.status, 'cancelled');

    const retry = await call(base, 'POST', `/internal/courses/course-1/jobs/${created.body.id}/retry`, {
      headers: headers(),
    });
    assert.equal(retry.status, 200);
    assert.equal(retry.body.status, 'queued');
    assert.equal(retry.body.progress, 0);
    assert.equal(JSON.stringify(retry.body).includes('api_key'), false);
  });
});

test('a job is invisible across users and courses', async () => {
  const { server } = harness();
  await withServer(server, async (base) => {
    const created = await call(base, 'POST', '/internal/courses/course-1/jobs', {
      body: { kind: 'generation', mode: 'quiz', input: { prompt: '复习' } },
      headers: headers({ extra: { 'idempotency-key': 'private-1' } }),
    });
    const otherUser = await call(base, 'GET', `/internal/courses/course-1/jobs/${created.body.id}`, {
      headers: headers({ sub: 'user-2' }),
    });
    assert.equal(otherUser.status, 404);
    const otherCourse = await call(base, 'GET', `/internal/courses/course-2/jobs/${created.body.id}`, {
      headers: headers({ courseId: 'course-2' }),
    });
    assert.equal(otherCourse.status, 404);
  });
});
