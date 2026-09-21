import type { Capability } from '../capabilities.ts';
import type { ProviderConfig } from '../config.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import { prepareStage } from '../dsl/validate.ts';
import type { JobRow } from '../jobs/repository.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { JobRepository } from '../jobs/repository.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { hashRequest, WorkspaceRepository } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER, stageResponse } from '../workspace/routes.ts';
import { GENERATION_MODES, buildGeneratedStage, isGenerationMode } from './generator.ts';

export const GENERATION_SCOPE = 'generation:write';
export const GENERATION_CAPABILITY: Capability = 'generation';

function parseBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body) throw new WorkspaceError('invalid_request', 'request body is required');
  let value: unknown;
  try { value = JSON.parse(request.body.toString('utf8')); } catch { throw new WorkspaceError('invalid_request', 'request body is not valid JSON'); }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new WorkspaceError('invalid_request', 'request body must be an object');
  return value as Record<string, unknown>;
}

function selectedRoleIds(body: Record<string, unknown>): string[] {
  if (!Array.isArray(body.selected_role_ids)) return [];
  return [...new Set(body.selected_role_ids
    .filter((value): value is string => typeof value === 'string' && value.trim())
    .map((value) => value.trim()))].slice(0, 7);
}

function roleMode(body: Record<string, unknown>): 'preset' | 'auto' {
  return body.role_mode === 'auto' ? 'auto' : 'preset';
}

function respond(work: () => RouteResponse): RouteResponse {
  try { return work(); } catch (error) {
    if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
    throw error;
  }
}

function jobBody(job: JobRow): Record<string, unknown> {
  return { id: job.id, status: job.status, progress: job.progress, artifact_id: job.artifact_id, mode: job.mode, error_code: job.error_code };
}

export function createGenerationRoutes(options: { database: ServiceDatabase; provider?: ProviderConfig; now?: () => string }): RouteDefinition[] {
  const workspaceRepository = new WorkspaceRepository(options.database);
  const jobs = new JobRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  return [{
    method: 'POST',
    pattern: '/internal/courses/:courseId/workspaces/:workspaceId/generate',
    scopes: [GENERATION_SCOPE, 'workspace:write', 'job:write'],
    courseScoped: true,
    capabilities: [GENERATION_CAPABILITY],
    handler: (request) => respond(() => {
      const body = parseBody(request);
      const mode = body.mode;
      if (!isGenerationMode(mode)) throw new WorkspaceError('invalid_request', `mode must be one of ${GENERATION_MODES.join(', ')}`);
      const prompt = typeof body.prompt === 'string' ? body.prompt.trim() : '';
      if (!prompt) throw new WorkspaceError('invalid_request', 'prompt is required');
      if (prompt.length > 2000) throw new WorkspaceError('invalid_request', 'prompt is too long');
      const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
      if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
      const userId = request.claims.sub;
      const courseId = request.params.courseId ?? '';
      const workspaceId = request.params.workspaceId ?? '';
      const requestHash = hashRequest(body);
      const replay = idempotency.lookup(userId, key, requestHash);
      if (replay) {
        // A provider job keeps moving after the first response was recorded;
        // the replay must reflect the live state, not the moment of enqueue.
        const jobId = typeof replay.body.job_id === 'string' ? replay.body.job_id : null;
        if (jobId) {
          try {
            replay.body = { ...replay.body, job: jobBody(jobs.get({ userId, courseId, jobId })) };
          } catch { /* the job is gone; hand back the recorded response as-is */ }
        }
        return replay;
      }

      workspaceRepository.getWorkspace({ userId, courseId, workspaceId });
      const agentIds = roleMode(body) === 'preset' ? selectedRoleIds(body) : [];
      if (options.provider) {
        // Real generation is asynchronous: enqueue and let the worker run the
        // upstream call, then clients poll the job.
        const job = jobs.create({ userId, courseId, kind: 'generation', mode, request: { ...body, workspace_id: workspaceId }, now: now() });
        const response: RouteResponse = {
          status: 201,
          body: { job_id: job.id, job: jobBody(job), source: 'provider', mode },
        };
        idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
        return response;
      }
      const job = jobs.create({ userId, courseId, kind: 'generation', mode, request: body, now: now() });
      jobs.markRunning({ userId, courseId, jobId: job.id, now: now() });
      const prepared = prepareStage(buildGeneratedStage(mode, prompt, Date.now(), { agentIds }));
      const stage = workspaceRepository.createStage({
        userId, courseId, workspaceId, title: prompt.slice(0, 200),
        document: prepared.document, dslVersion: prepared.document.dslVersion, now: now(),
      });
      const completed = jobs.complete({
        userId, courseId, jobId: job.id,
        artifact: { filename: `${prompt.slice(0, 40) || '学习内容'}.stage.json`, mediaType: 'application/json', payload: Buffer.from(JSON.stringify(prepared.document), 'utf8') },
        now: now(),
      });
      const response: RouteResponse = {
        status: 201,
        body: {
          stage_id: stage.id,
          stage: stageResponse(stage, { includeDocument: true }),
          job: jobBody(completed),
          source: 'local-template',
        },
      };
      idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
      return response;
    }),
  }];
}
