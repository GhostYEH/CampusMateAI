import { createServer as createHttpServer } from 'node:http';

export type ReadinessState = Record<string, boolean>;

export interface ServiceDependencies {
  readiness?: () => Promise<ReadinessState> | ReadinessState;
}

function sendJson(response, statusCode: number, body: Record<string, unknown>) {
  const payload = JSON.stringify(body);
  response.statusCode = statusCode;
  response.setHeader('content-type', 'application/json; charset=utf-8');
  response.setHeader('cache-control', 'no-store');
  response.end(payload);
}

export function createServer(dependencies: ServiceDependencies = {}) {
  const readiness = dependencies.readiness ?? (() => ({ runtime: true }));

  return createHttpServer(async (request, response) => {
    const method = request.method ?? 'GET';
    const pathname = new URL(request.url ?? '/', 'http://openmaic.internal').pathname;

    if (method !== 'GET') {
      sendJson(response, 405, { error: 'method_not_allowed' });
      return;
    }

    if (pathname === '/internal/health/live') {
      sendJson(response, 200, { status: 'ok' });
      return;
    }

    if (pathname === '/internal/health/ready') {
      try {
        const dependenciesState = await readiness();
        const ready = Object.values(dependenciesState).every(Boolean);
        sendJson(response, ready ? 200 : 503, {
          status: ready ? 'ready' : 'degraded',
          dependencies: dependenciesState,
        });
      } catch {
        sendJson(response, 503, { status: 'degraded', dependencies: { runtime: false } });
      }
      return;
    }

    sendJson(response, 404, { error: 'not_found' });
  });
}
