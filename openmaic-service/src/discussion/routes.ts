import type { Capability } from '../capabilities.ts';
import type { ProviderConfig } from '../config.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { JobRepository } from '../jobs/repository.ts';
import { hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER } from '../workspace/routes.ts';
import { WorkspaceError } from '../workspace/errors.ts';

export const DISCUSSION_SCOPE = 'multi-agent:write';
export const DISCUSSION_CAPABILITY: Capability = 'multi-agent';

function parseBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body || request.body.length === 0) throw new WorkspaceError('invalid_request', 'request body is required');
  let value: unknown;
  try { value = JSON.parse(request.body.toString('utf8')); } catch { throw new WorkspaceError('invalid_request', 'request body is not valid JSON'); }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new WorkspaceError('invalid_request', 'request body must be an object');
  return value as Record<string, unknown>;
}

function requiredPrompt(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) throw new WorkspaceError('invalid_request', 'prompt is required');
  if (value.trim().length > 4_000) throw new WorkspaceError('invalid_request', 'prompt is too long');
  return value.trim();
}

export function createDiscussionRoutes(options: { database: ServiceDatabase; provider?: ProviderConfig; available?: boolean; now?: () => string }): RouteDefinition[] {
  const available = options.available ?? Boolean(options.provider);
  const jobs = new JobRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  return [{
    method: 'POST', pattern: '/internal/courses/:courseId/discussion', scopes: [DISCUSSION_SCOPE], courseScoped: true, capabilities: available ? [DISCUSSION_CAPABILITY] : [],
    handler: (request): RouteResponse => {
      try {
        const body = parseBody(request);
        const prompt = requiredPrompt(body.prompt);
        if (!available || !options.provider) {
          return { status: 503, body: { error: 'provider_unavailable', message: 'multi-agent provider is unavailable' } };
        }
        const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
        if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
        const userId = request.claims.sub;
        const courseId = request.params.courseId ?? '';
        const requestHash = hashRequest(body);
        const replay = idempotency.lookup(userId, key, requestHash);
        if (replay) return replay;
        const job = jobs.create({
          userId, courseId, kind: 'discussion', mode: options.provider.model,
          request: { prompt }, now: now(),
        });
        const response: RouteResponse = {
          status: 202,
          body: {
            job_id: job.id,
            job: { id: job.id, status: job.status, progress: job.progress, artifact_id: job.artifact_id, mode: job.mode, error_code: job.error_code },
          },
        };
        idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
        return response;
      } catch (error) {
        if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
        throw error;
      }
    },
  }];
}
