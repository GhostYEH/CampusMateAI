import { createServer as createHttpServer, type IncomingMessage, type ServerResponse } from 'node:http';

import type { ServiceAuthenticator } from './auth/authenticator.ts';
import { normalizeCapabilities, type Capability } from './capabilities.ts';
import type { ServiceDatabase } from './db/database.ts';
import { ServiceAssertionError, type ServiceAssertionClaims } from './serviceAssertion.ts';

export const ASSERTION_HEADER = 'x-campusmate-service-assertion';
/**
 * Transport-level body cap.
 *
 * Must stay **above** `DSL_LIMITS.maxDocumentBytes`: if it were lower, the
 * transport would answer first and the DSL's named `maxDocumentBytes` rejection
 * could never be reached — the limit would be documentation rather than
 * behaviour. `tests/workspace.test.mjs` pins that ordering.
 */
export const MAX_REQUEST_BODY_BYTES = 4 * 1024 * 1024;

export type ReadinessState = Record<string, boolean>;

export interface RouteRequest {
  method: string;
  url: URL;
  params: Record<string, string>;
  claims: ServiceAssertionClaims;
  body: Buffer | null;
  /** Lower-cased request headers; absent headers read as `undefined`. */
  headers: Record<string, string | undefined>;
}

export interface RouteResponse {
  status: number;
  body: Record<string, unknown>;
}

export interface RouteDefinition {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  /** Express-style path with `:name` segments, e.g. `/internal/courses/:courseId`. */
  pattern: string;
  scopes: string[];
  /** When true the `:courseId` param must match the assertion's `course_id`. */
  courseScoped: boolean;
  capabilities: Capability[];
  /**
   * Handlers are synchronous on purpose: the jti consumption and the handler's
   * own writes share one SQLite transaction, and a transaction cannot span an
   * `await` with a synchronous driver.
   */
  handler: (request: RouteRequest) => RouteResponse;
}

export interface ServiceDependencies {
  authenticator: ServiceAuthenticator;
  readiness: () => ReadinessState;
  routes?: RouteDefinition[];
  database?: ServiceDatabase;
  now?: () => number;
}

interface MatchedRoute {
  route: RouteDefinition;
  params: Record<string, string>;
}

function sendJson(response: ServerResponse, statusCode: number, body: Record<string, unknown>) {
  response.statusCode = statusCode;
  response.setHeader('content-type', 'application/json; charset=utf-8');
  response.setHeader('cache-control', 'no-store');
  response.end(JSON.stringify(body));
}

function patternToRegExp(pattern: string) {
  const segments = pattern.split('/').map((segment) => {
    if (segment.startsWith(':')) return `(?<${segment.slice(1)}>[^/]+)`;
    return segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  });
  return new RegExp(`^${segments.join('/')}$`);
}

/**
 * Find the route for a request.
 *
 * A pattern match alone is not enough: several methods share one path shape
 * (`GET`/`POST` on a collection, `GET`/`PATCH`/`DELETE` on a member), so a
 * pattern-first lookup would answer 405 for a method that *is* mounted further
 * down the list. The method is therefore part of the search; the first
 * path-only match is kept so a genuinely unsupported method still gets a 405
 * rather than a 404.
 */
function matchRoute(
  compiled: Array<{ route: RouteDefinition; matcher: RegExp }>,
  pathname: string,
  method: string,
): MatchedRoute | null {
  let pathOnly: MatchedRoute | null = null;
  for (const entry of compiled) {
    const match = entry.matcher.exec(pathname);
    if (!match) continue;
    const params = { ...(match.groups ?? {}) };
    if (entry.route.method === method) return { route: entry.route, params };
    pathOnly ??= { route: entry.route, params };
  }
  return pathOnly;
}

/**
 * Authorisation failures become `forbidden`; credential failures become
 * `unauthorized`. Neither branch echoes the assertion, the secret, or the
 * expected audience.
 */
function statusForAssertionError(error: ServiceAssertionError): number {
  if (error.code === 'assertion_scope' || error.code === 'assertion_course') return 403;
  return 401;
}

async function readBody(request: IncomingMessage): Promise<Buffer | null> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > MAX_REQUEST_BODY_BYTES) {
      throw Object.assign(new Error('payload too large'), { tooLarge: true });
    }
    chunks.push(buffer);
  }
  return chunks.length ? Buffer.concat(chunks) : null;
}

export function createServer(dependencies: ServiceDependencies) {
  const compiled = (dependencies.routes ?? []).map((route) => ({ route, matcher: patternToRegExp(route.pattern) }));
  // The advertised set is exactly the set declared by mounted route modules, so
  // an unimplemented capability can never reach the browser.
  const capabilities = normalizeCapabilities(compiled.flatMap((entry) => entry.route.capabilities));
  const now = dependencies.now ?? (() => Math.floor(Date.now() / 1000));

  return createHttpServer(async (request, response) => {
    const method = request.method ?? 'GET';
    const pathname = new URL(request.url ?? '/', 'http://openmaic.internal').pathname;

    // The only anonymous endpoint: a liveness probe that reveals nothing and
    // touches no dependency.
    if (pathname === '/internal/health/live') {
      if (method !== 'GET') {
        sendJson(response, 405, { error: 'method_not_allowed' });
        return;
      }
      sendJson(response, 200, { status: 'ok' });
      return;
    }

    if (!pathname.startsWith('/internal/')) {
      // No public surface, and no hint that anything else exists.
      sendJson(response, 404, { error: 'not_found' });
      return;
    }

    const isReady = pathname === '/internal/health/ready';
    const matched = isReady ? null : matchRoute(compiled, pathname, method);
    const requiredScopes = isReady ? ['service:status'] : (matched?.route.scopes ?? []);
    // `null` means "this route is not course-scoped", so the claim's course is
    // deliberately not compared. Only a `:courseId` route binds the assertion.
    const expectedCourseId =
      matched && matched.route.courseScoped ? (matched.params.courseId ?? '') : null;

    const rawHeader = request.headers[ASSERTION_HEADER];
    const token = Array.isArray(rawHeader) ? rawHeader[0] : rawHeader;

    // Cheap pre-check so an unauthenticated caller cannot make us buffer a body.
    if (!token) {
      sendJson(response, 401, { error: 'unauthorized' });
      return;
    }

    let body: Buffer | null = null;
    if (matched && matched.route.method !== 'GET') {
      try {
        body = await readBody(request);
      } catch (error) {
        const tooLarge = Boolean(error && typeof error === 'object' && 'tooLarge' in error);
        sendJson(response, tooLarge ? 413 : 400, { error: tooLarge ? 'payload_too_large' : 'invalid_request' });
        return;
      }
    }

    const execute = (): RouteResponse => {
      const claims = dependencies.authenticator.authorize({ token, requiredScopes, expectedCourseId, now: now() });
      if (isReady) return readinessResponse(dependencies, capabilities);
      if (!matched) return { status: 404, body: { error: 'not_found' } };
      if (matched.route.method !== method) return { status: 405, body: { error: 'method_not_allowed' } };
      const url = new URL(request.url ?? '/', 'http://openmaic.internal');
      const headers: Record<string, string | undefined> = {};
      for (const [name, value] of Object.entries(request.headers)) {
        headers[name.toLowerCase()] = Array.isArray(value) ? value[0] : value;
      }
      return matched.route.handler({ method, url, params: matched.params, claims, body, headers });
    };

    try {
      const result = dependencies.database ? dependencies.database.transaction(execute) : execute();
      sendJson(response, result.status, result.body);
    } catch (error) {
      if (error instanceof ServiceAssertionError) {
        const status = statusForAssertionError(error);
        sendJson(response, status, { error: status === 403 ? 'forbidden' : 'unauthorized' });
        return;
      }
      sendJson(response, 500, { error: 'internal_error' });
    }
  });
}

function readinessResponse(dependencies: ServiceDependencies, capabilities: Capability[]): RouteResponse {
  try {
    const state = dependencies.readiness();
    const ready = Object.values(state).every(Boolean);
    return {
      status: ready ? 200 : 503,
      body: {
        status: ready ? 'ready' : 'degraded',
        reason: ready ? 'ready' : 'dependency_unavailable',
        dependencies: state,
        capabilities: ready ? capabilities : [],
      },
    };
  } catch {
    return {
      status: 503,
      body: { status: 'degraded', reason: 'dependency_unavailable', dependencies: {}, capabilities: [] },
    };
  }
}
