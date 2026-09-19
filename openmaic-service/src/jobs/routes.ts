import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { hashRequest } from '../workspace/repository.ts';
import { JobRepository, type JobRow } from './repository.ts';

export const JOB_READ_SCOPE = 'job:read';
export const JOB_WRITE_SCOPE = 'job:write';
export const JOB_CANCEL_SCOPE = 'job:cancel';
export const JOB_CAPABILITY: Capability = 'generation';

function parseBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body || request.body.length === 0) throw new WorkspaceError('invalid_request', 'request body is required');
  let value: unknown;
  try { value = JSON.parse(request.body.toString('utf8')); } catch { throw new WorkspaceError('invalid_request', 'request body is not valid JSON'); }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new WorkspaceError('invalid_request', 'request body must be an object');
  return value as Record<string, unknown>;
}

function requiredString(value: unknown, field: string, max = 80): string {
  if (typeof value !== 'string' || !value.trim()) throw new WorkspaceError('invalid_request', `${field} is required`);
  const text = value.trim();
  if (text.length > max) throw new WorkspaceError('invalid_request', `${field} is too long`);
  return text;
}

function jobResponse(row: JobRow): Record<string, unknown> {
  return {
    id: row.id,
    course_id: row.course_id,
    kind: row.kind,
    mode: row.mode,
    status: row.status,
    progress: Number(row.progress),
    attempts: Number(row.attempts),
    error_code: row.error_code,
    artifact_id: row.artifact_id,
    created_at: row.created_at,
    updated_at: row.updated_at,
    started_at: row.started_at,
    finished_at: row.finished_at,
  };
}

function respond(work: () => RouteResponse): RouteResponse {
  try { return work(); } catch (error) {
    if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
    throw error;
  }
}

export function createJobRoutes(options: { database: ServiceDatabase; now?: () => string }): RouteDefinition[] {
  const repository = new JobRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());
  const actor = (request: RouteRequest) => ({ userId: request.claims.sub, courseId: request.params.courseId ?? '' });
  const withIdempotency = (request: RouteRequest, body: unknown, work: () => RouteResponse): RouteResponse => {
    const key = request.headers['idempotency-key']?.trim();
    if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
    if (key.length > 200) throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');
    const identity = actor(request);
    const hash = hashRequest(body);
    const replay = idempotency.lookup(identity.userId, key, hash);
    if (replay) return replay;
    const response = work();
    idempotency.record(identity.userId, key, { courseId: identity.courseId, method: request.method, path: request.url.pathname }, hash, response);
    return response;
  };

  return [
    {
      method: 'POST', pattern: '/internal/courses/:courseId/jobs', scopes: [JOB_WRITE_SCOPE], courseScoped: true, capabilities: [JOB_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseBody(request);
        const kind = requiredString(body.kind, 'kind');
        const mode = requiredString(body.mode ?? body.format ?? 'default', 'mode');
        return withIdempotency(request, body, () => {
          const identity = actor(request);
          const row = repository.create({ userId: identity.userId, courseId: identity.courseId, kind, mode, request: body, now: now() });
          return { status: 201, body: jobResponse(row) };
        });
      }),
    },
    {
      method: 'GET', pattern: '/internal/courses/:courseId/jobs/:jobId', scopes: [JOB_READ_SCOPE], courseScoped: true, capabilities: [JOB_CAPABILITY],
      handler: (request) => respond(() => { const identity = actor(request); return { status: 200, body: jobResponse(repository.get({ ...identity, jobId: request.params.jobId ?? '' })) }; }),
    },
    {
      method: 'POST', pattern: '/internal/courses/:courseId/jobs/:jobId/cancel', scopes: [JOB_CANCEL_SCOPE], courseScoped: true, capabilities: [JOB_CAPABILITY],
      handler: (request) => respond(() => { const identity = actor(request); return { status: 200, body: jobResponse(repository.cancel({ ...identity, jobId: request.params.jobId ?? '', now: now() })) }; }),
    },
    {
      method: 'POST', pattern: '/internal/courses/:courseId/jobs/:jobId/retry', scopes: [JOB_WRITE_SCOPE], courseScoped: true, capabilities: [JOB_CAPABILITY],
      handler: (request) => respond(() => { const identity = actor(request); return { status: 200, body: jobResponse(repository.retry({ ...identity, jobId: request.params.jobId ?? '', now: now() })) }; }),
    },
    {
      method: 'GET', pattern: '/internal/courses/:courseId/artifacts/:artifactId', scopes: [JOB_READ_SCOPE], courseScoped: true, capabilities: [JOB_CAPABILITY],
      handler: (request) => respond(() => {
        const identity = actor(request);
        const artifact = repository.getArtifact({ ...identity, artifactId: request.params.artifactId ?? '' });
        return { status: 200, body: { id: artifact.id, job_id: artifact.job_id, filename: artifact.filename, media_type: artifact.media_type, byte_size: artifact.byte_size, sha256: artifact.sha256, content_base64: Buffer.from(artifact.payload).toString('base64') } };
      }),
    },
  ];
}
