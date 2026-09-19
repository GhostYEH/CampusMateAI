import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import { prepareStage } from '../dsl/validate.ts';
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

function respond(work: () => RouteResponse): RouteResponse {
  try { return work(); } catch (error) {
    if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
    throw error;
  }
}

export function createGenerationRoutes(options: { database: ServiceDatabase; now?: () => string }): RouteDefinition[] {
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
      if (replay) return replay;

      workspaceRepository.getWorkspace({ userId, courseId, workspaceId });
      const job = jobs.create({ userId, courseId, kind: 'generation', mode, request: body, now: now() });
      jobs.markRunning({ userId, courseId, jobId: job.id, now: now() });
      const prepared = prepareStage(buildGeneratedStage(mode, prompt));
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
          job: { id: completed.id, status: completed.status, progress: completed.progress, artifact_id: completed.artifact_id, mode: completed.mode },
          source: 'local-template',
        },
      };
      idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
      return response;
    }),
  }];
}
