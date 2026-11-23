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
import { isAssignmentReviewSpec } from './assignment-review.ts';

export const GENERATION_SCOPE = 'generation:write';
export const GENERATION_CAPABILITY: Capability = 'generation';
const COURSE_CONTEXT_SEPARATOR = '\n\n请结合以下已授权课程上下文生成内容：\n';

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

function normalizedTopic(topic: string): string {
  return topic.trim().replace(/\s+/g, ' ');
}

function legacyHomeTopic(input: Record<string, unknown>): string | null {
  if (input.home_topic !== undefined || input.mode !== 'adaptive' || typeof input.prompt !== 'string' ||
      input.role_mode !== 'preset' || !Array.isArray(input.selected_role_ids) || input.selected_role_ids.length) return null;
  const boundary = input.prompt.indexOf(COURSE_CONTEXT_SEPARATOR);
  return boundary < 0 ? null : normalizedTopic(input.prompt.slice(0, boundary));
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
      const homeTopic = typeof body.home_topic === 'string' ? normalizedTopic(body.home_topic) : '';
      if (body.home_topic !== undefined && (mode !== 'adaptive' || !homeTopic || homeTopic.length > 1500)) {
        throw new WorkspaceError('invalid_request', 'home_topic requires adaptive mode and a valid learner topic');
      }
      if (body.assignment_review !== undefined && (!isAssignmentReviewSpec(body.assignment_review) || mode !== 'quiz')) throw new WorkspaceError('invalid_request', 'assignment_review requires quiz mode, a positive question_count, and valid source numbers/stems');
      if (body.assignment_review && !options.provider) throw new WorkspaceError('invalid_request', 'assignment review requires a real generation provider');
      const prompt = typeof body.prompt === 'string' ? body.prompt.trim() : '';
      if (!prompt) throw new WorkspaceError('invalid_request', 'prompt is required');
      // The trusted gateway also supplies full, authorized homework snapshots.
      // Browser-authored prompts remain capped at 2,000 by the public API.
      if (prompt.length > 24000) throw new WorkspaceError('invalid_request', 'prompt is too long');
      const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
      if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
      const userId = request.claims.sub;
      const courseId = request.params.courseId ?? '';
      const workspaceId = request.params.workspaceId ?? '';
      const scope = { courseId, method: request.method, path: request.url.pathname };
      // A home replay identifies the learner's original request. The course
      // snapshot and the latest workspace can both change after submission.
      const requestHash = hashRequest(homeTopic ? { mode, home_topic: homeTopic } : body);
      const replay = idempotency.get(userId, key);
      if (replay) {
        if (replay.scope.courseId !== courseId || replay.scope.method !== scope.method ||
            (!homeTopic && (replay.scope.path !== scope.path || replay.requestHash !== requestHash))) {
          throw new WorkspaceError('idempotency_conflict');
        }
        // A provider job keeps moving after the first response was recorded;
        // the replay must reflect the live state, not the moment of enqueue.
        const jobId = typeof replay.body.job_id === 'string' ? replay.body.job_id : null;
        if (homeTopic) {
          if (!jobId) throw new WorkspaceError('idempotency_conflict');
          const job = jobs.get({ userId, courseId, jobId });
          const input = JSON.parse(job.input_json ?? '{}') as Record<string, unknown>;
          const original = typeof input.workspace_id === 'string' ? input.workspace_id : '';
          const matchesLegacy = key.endsWith(':generation') && legacyHomeTopic(input) === homeTopic;
          if (job.kind !== 'generation' || !original || !replay.scope.path.endsWith(`/workspaces/${original}/generate`) ||
              (replay.requestHash !== requestHash && !matchesLegacy)) throw new WorkspaceError('idempotency_conflict');
          workspaceRepository.getWorkspace({ userId, courseId, workspaceId: original });
          return { status: replay.status, body: { ...replay.body, job: jobBody(job), workspace_id: original } };
        }
        if (jobId) {
          try {
            replay.body = { ...replay.body, job: jobBody(jobs.get({ userId, courseId, jobId })) };
          } catch { /* the job is gone; hand back the recorded response as-is */ }
        }
        return { status: replay.status, body: replay.body };
      }

      workspaceRepository.getWorkspace({ userId, courseId, workspaceId });
      if (mode === 'adaptive' && !options.provider) {
        return { status: 503, body: { error: 'provider_unavailable', message: '综合课堂需要可用的生成模型' } };
      }
      const agentIds = roleMode(body) === 'preset' ? selectedRoleIds(body) : [];
      if (options.provider) {
        // Real generation is asynchronous: enqueue and let the worker run the
        // upstream call, then clients poll the job.
        const job = jobs.create({ userId, courseId, kind: 'generation', mode, request: { ...body, workspace_id: workspaceId }, now: now() });
        const response: RouteResponse = {
          status: 201,
          body: { job_id: job.id, job: jobBody(job), source: 'provider', mode, ...(homeTopic && { workspace_id: workspaceId }) },
        };
        idempotency.record(userId, key, scope, requestHash, response);
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
      idempotency.record(userId, key, scope, requestHash, response);
      return response;
    }),
  }];
}
