import type { Capability } from '../capabilities.ts';
import type { TtsConfig } from '../config.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { JobRepository } from '../jobs/repository.ts';
import { hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER } from '../workspace/routes.ts';
import { WorkspaceError } from '../workspace/errors.ts';

export const TTS_SCOPE = 'tts:write';
export const TTS_CAPABILITY: Capability = 'tts';

function parseBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body || request.body.length === 0) throw new WorkspaceError('invalid_request', 'request body is required');
  let value: unknown;
  try { value = JSON.parse(request.body.toString('utf8')); } catch { throw new WorkspaceError('invalid_request', 'request body is not valid JSON'); }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new WorkspaceError('invalid_request', 'request body must be an object');
  return value as Record<string, unknown>;
}

function requiredText(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) throw new WorkspaceError('invalid_request', 'text is required');
  if (value.trim().length > 20_000) throw new WorkspaceError('invalid_request', 'text is too long');
  return value.trim();
}

function optionalText(value: unknown, name: string, max: number): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'string') throw new WorkspaceError('invalid_request', `${name} must be a string`);
  const text = value.trim();
  if (!text) return undefined;
  if (text.length > max) throw new WorkspaceError('invalid_request', `${name} is too long`);
  return text;
}

function optionalVoice(value: unknown): string | undefined {
  const voice = optionalText(value, 'voice', 80);
  // eslint-disable-next-line no-control-regex
  if (voice && /[\u0000-\u001f]/.test(voice)) throw new WorkspaceError('invalid_request', 'voice must not contain control characters');
  return voice;
}

export function createTtsRoutes(options: { database: ServiceDatabase; tts?: TtsConfig; available?: boolean; now?: () => string }): RouteDefinition[] {
  // Explicit `available: false` keeps the truthful 503 for deployments that
  // want the route mounted without a provider; otherwise configuration wins.
  const available = options.available ?? Boolean(options.tts);
  const jobs = new JobRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  return [{
    method: 'POST', pattern: '/internal/courses/:courseId/tts', scopes: [TTS_SCOPE], courseScoped: true, capabilities: available ? [TTS_CAPABILITY] : [],
    handler: (request): RouteResponse => {
      try {
        const body = parseBody(request);
        const text = requiredText(body.text);
        const instruction = optionalText(body.instruction, 'instruction', 2000);
        const voice = optionalVoice(body.voice);
        if (!available || !options.tts) {
          return { status: 503, body: { error: 'provider_unavailable', message: 'tts provider is unavailable' } };
        }
        const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
        if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
        const userId = request.claims.sub;
        const courseId = request.params.courseId ?? '';
        const requestHash = hashRequest(body);
        const replay = idempotency.lookup(userId, key, requestHash);
        if (replay) return replay;
        const job = jobs.create({
          userId, courseId, kind: 'tts', mode: options.tts.model,
          request: { text, instruction, voice: voice ?? options.tts.voice }, now: now(),
        });
        const response: RouteResponse = {
          status: 202,
          body: {
            job_id: job.id,
            job: { id: job.id, status: job.status, progress: job.progress, artifact_id: job.artifact_id, mode: job.mode, error_code: job.error_code },
            voice: voice ?? options.tts.voice,
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
