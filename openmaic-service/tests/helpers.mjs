import { createHmac } from 'node:crypto';
import { randomUUID } from 'node:crypto';

import { ServiceAuthenticator } from '../src/auth/authenticator.ts';
import { ServiceDatabase } from '../src/db/database.ts';
import { SqliteReplayStore } from '../src/db/replayStore.ts';
import { createServer } from '../src/server.ts';

export const TEST_SECRET = 'test-secret';
export const ISSUER = 'campusmate-backend';
export const AUDIENCE = 'openmaic-service';

/** Mints an assertion shaped exactly like the one FastAPI issues. */
export function mintAssertion({
  sub = 'user-1',
  courseId = 'course-1',
  scopes = ['service:status'],
  iat,
  ttl = 60,
  jti,
  secret = TEST_SECRET,
  issuer = ISSUER,
  audience = AUDIENCE,
} = {}) {
  const issuedAt = iat ?? Math.floor(Date.now() / 1000);
  const payload = {
    iss: issuer,
    aud: audience,
    sub,
    course_id: courseId,
    scope: scopes,
    iat: issuedAt,
    exp: issuedAt + ttl,
    jti: jti ?? randomUUID(),
  };
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const signature = createHmac('sha256', secret).update(`${header}.${body}`).digest('base64url');
  return `${header}.${body}.${signature}`;
}

/** Builds a fully wired service over an in-memory database. */
export function createHarness({
  routes = [],
  readiness = () => ({ runtime: true, database: true }),
  now,
  database,
} = {}) {
  const store = database ?? new ServiceDatabase(':memory:');
  const replayStore = new SqliteReplayStore(store);
  const authenticator = new ServiceAuthenticator({ secret: TEST_SECRET, replayStore, now });
  const server = createServer({ authenticator, database: store, readiness, routes, now });
  return { database: store, replayStore, authenticator, server };
}

export async function withServer(server, fn) {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const { port } = server.address();
    return await fn(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
  }
}

/** A course-scoped route used to prove per-course binding. */
export function courseScopedRoute(handler = () => ({ status: 200, body: { ok: true } })) {
  return {
    method: 'GET',
    pattern: '/internal/courses/:courseId/workspaces',
    scopes: ['workspace:read'],
    courseScoped: true,
    capabilities: ['workspace'],
    handler,
  };
}
