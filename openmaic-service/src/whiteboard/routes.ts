import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import { DslLimitError } from '../dsl/limits.ts';
import { DslValidationError, prepareStage } from '../dsl/validate.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { hashRequest, WorkspaceRepository } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER, IF_MATCH_HEADER, stageResponse } from '../workspace/routes.ts';

export const WHITEBOARD_WRITE_SCOPE = 'stage:write';
export const WHITEBOARD_CAPABILITY: Capability = 'whiteboard';
const MAX_ELEMENTS = 500;

function parseBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body) throw new WorkspaceError('invalid_request', 'request body is required');
  let value: unknown;
  try { value = JSON.parse(request.body.toString('utf8')); } catch { throw new WorkspaceError('invalid_request', 'request body is not valid JSON'); }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new WorkspaceError('invalid_request', 'request body must be an object');
  return value as Record<string, unknown>;
}

function revision(request: RouteRequest): number {
  const raw = request.headers[IF_MATCH_HEADER]?.replaceAll('"', '').trim();
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 1) throw new WorkspaceError('invalid_request', 'If-Match must be a positive integer revision');
  return value;
}

function board(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new WorkspaceError('invalid_request', 'board must be an object');
  const input = value as Record<string, unknown>;
  if (typeof input.id !== 'string' || !input.id.trim()) throw new WorkspaceError('invalid_request', 'board.id is required');
  if (typeof input.title !== 'string' || !input.title.trim()) throw new WorkspaceError('invalid_request', 'board.title is required');
  if (!Array.isArray(input.elements) || input.elements.length > MAX_ELEMENTS) throw new WorkspaceError('invalid_request', 'board.elements must be a bounded array');
  return { id: input.id.trim(), title: input.title.trim(), elements: input.elements };
}

function respond(work: () => RouteResponse): RouteResponse {
  try { return work(); } catch (error) {
    if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
    if (error instanceof DslLimitError) return { status: 422, body: { error: 'document_rejected', message: error.message, limit: error.limit } };
    if (error instanceof DslValidationError) return { status: 422, body: { error: 'document_rejected', message: error.message, issues: error.issues } };
    throw error;
  }
}

export function createWhiteboardRoutes(options: { database: ServiceDatabase; now?: () => string }): RouteDefinition[] {
  const repository = new WorkspaceRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());
  return [{
    method: 'POST', pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/whiteboard',
    scopes: [WHITEBOARD_WRITE_SCOPE], courseScoped: true, capabilities: [WHITEBOARD_CAPABILITY],
    handler: (request) => respond(() => {
      const body = parseBody(request);
      const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
      if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
      const userId = request.claims.sub;
      const courseId = request.params.courseId ?? '';
      const workspaceId = request.params.workspaceId ?? '';
      const stageId = request.params.stageId ?? '';
      const requestHash = hashRequest(body);
      const replay = idempotency.lookup(userId, key, requestHash);
      if (replay) return replay;
      const current = repository.getStage({ userId, courseId, workspaceId, stageId });
      const document = JSON.parse(current.document) as Record<string, unknown>;
      const stage = (document.stage && typeof document.stage === 'object' ? document.stage : {}) as Record<string, unknown>;
      const existing = Array.isArray(stage.whiteboard) ? stage.whiteboard : [];
      const prepared = prepareStage({ ...document, stage: { ...stage, whiteboard: [...existing, board(body.board)] } });
      const updated = repository.replaceStage({ userId, courseId, workspaceId, stageId, expectedRevision: revision(request), document: prepared.document, dslVersion: prepared.document.dslVersion, now: now() });
      const response: RouteResponse = { status: 200, body: stageResponse(updated, { includeDocument: true }) };
      idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
      return response;
    }),
  }];
}
