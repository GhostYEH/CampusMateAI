/**
 * Internal workspace/stage routes.
 *
 * These are the only way the gateway can read or write a student's learning
 * content, so three rules are enforced here rather than trusted to callers:
 *
 * - the `:courseId` in the path is the one the assertion was minted for (the
 *   server compares it before the handler runs), and the acting user always
 *   comes from the assertion's `sub` — never from the body;
 * - a mutating request that needs to be safe to retry must carry an
 *   `Idempotency-Key`; the stored response is replayed verbatim, and the same key
 *   with a different body is a conflict instead of a silent overwrite;
 * - a conditional update must carry `If-Match`; a mismatch is a conflict, and a
 *   missing one is refused rather than treated as "overwrite anyway".
 */

import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import {
  DslLimitError,
  DslValidationError,
  DslVersionError,
  prepareStage,
} from '../dsl/index.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from './errors.ts';
import {
  WorkspaceRepository,
  hashRequest,
  type StageRow,
  type WorkspaceRow,
} from './repository.ts';

export const WORKSPACE_READ_SCOPE = 'workspace:read';
export const WORKSPACE_WRITE_SCOPE = 'workspace:write';
export const WORKSPACE_CAPABILITY: Capability = 'workspace';

export const IDEMPOTENCY_HEADER = 'idempotency-key';
export const IF_MATCH_HEADER = 'if-match';

function toWorkspace(row: WorkspaceRow): Record<string, unknown> {
  return {
    id: row.id,
    course_id: row.course_id,
    name: row.name,
    description: row.description,
    revision: Number(row.revision),
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

/**
 * `document` is omitted from list responses on purpose: a stage document can be
 * megabytes, and a list is a navigation surface. Clients fetch the single stage
 * they are about to open.
 */
function toStage(row: StageRow, options: { includeDocument: boolean }): Record<string, unknown> {
  const base: Record<string, unknown> = {
    id: row.id,
    workspace_id: row.workspace_id,
    course_id: row.course_id,
    title: row.title,
    revision: Number(row.revision),
    dsl_version: row.dsl_version,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
  if (options.includeDocument) base.document = JSON.parse(row.document) as unknown;
  return base;
}

function parseJsonBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body || request.body.length === 0) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(request.body.toString('utf8'));
  } catch {
    throw new WorkspaceError('invalid_request', 'request body is not valid JSON');
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new WorkspaceError('invalid_request', 'request body must be a JSON object');
  }
  return parsed as Record<string, unknown>;
}

function requireString(value: unknown, field: string, maxLength = 200): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new WorkspaceError('invalid_request', `${field} is required`);
  }
  const trimmed = value.trim();
  if (trimmed.length > maxLength) {
    throw new WorkspaceError('invalid_request', `${field} is too long`);
  }
  return trimmed;
}

function optionalString(value: unknown, field: string, maxLength = 4000): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== 'string') throw new WorkspaceError('invalid_request', `${field} must be a string`);
  if (value.length > maxLength) throw new WorkspaceError('invalid_request', `${field} is too long`);
  return value;
}

/**
 * Read `If-Match`. Accepts the quoted form (`"3"`) and the bare form (`3`),
 * because the gateway is the only client and both spellings occur in practice;
 * `*` is refused because "match anything" is exactly the lost-update this header
 * exists to prevent.
 */
function requireIfMatch(request: RouteRequest): number {
  const raw = request.headers[IF_MATCH_HEADER];
  if (!raw) throw new WorkspaceError('invalid_request', 'If-Match is required for this request');
  const normalized = raw.trim().replace(/^W\//, '').replaceAll('"', '');
  if (normalized === '*') {
    throw new WorkspaceError('invalid_request', 'If-Match: * is not accepted; send the revision you read');
  }
  const revision = Number(normalized);
  if (!Number.isInteger(revision) || revision < 1) {
    throw new WorkspaceError('invalid_request', 'If-Match must be a positive integer revision');
  }
  return revision;
}

function readLimit(request: RouteRequest): number | undefined {
  const raw = request.url.searchParams.get('limit');
  if (raw === null) return undefined;
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new WorkspaceError('invalid_request', 'limit must be a number');
  return value;
}

/** Map every expected failure onto its own status instead of a generic 500. */
function respond(work: () => RouteResponse): RouteResponse {
  try {
    return work();
  } catch (error) {
    if (error instanceof WorkspaceError) {
      return { status: error.status, body: { error: error.code, message: error.message } };
    }
    if (error instanceof DslLimitError) {
      return {
        status: 422,
        body: { error: 'document_rejected', message: error.message, limit: error.limit },
      };
    }
    if (error instanceof DslValidationError) {
      return {
        status: 422,
        body: { error: 'document_rejected', message: error.message, issues: error.issues },
      };
    }
    if (error instanceof DslVersionError) {
      return { status: 422, body: { error: 'document_rejected', message: error.message } };
    }
    throw error;
  }
}

export interface WorkspaceRouteOptions {
  database: ServiceDatabase;
  /** Injected so tests can pin timestamps and ids without patching globals. */
  now?: () => string;
}

export function createWorkspaceRoutes(options: WorkspaceRouteOptions): RouteDefinition[] {
  const repository = new WorkspaceRepository(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  /**
   * Run a mutating operation under the caller's idempotency key.
   *
   * The lookup, the write and the record all happen inside the request
   * transaction (the server wraps every handler), so a crash between them cannot
   * leave a key recorded without its effect, or an effect without its key.
   */
  function withIdempotency(
    request: RouteRequest,
    body: unknown,
    work: () => RouteResponse,
  ): RouteResponse {
    const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
    if (!key) {
      throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
    }
    if (key.length > 200) throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');
    const userId = request.claims.sub;
    const requestHash = hashRequest(body);
    const replay = repository.lookupIdempotency(userId, key, requestHash);
    if (replay) return replay;
    const response = work();
    repository.recordIdempotency(
      userId,
      key,
      { courseId: request.params.courseId ?? '', method: request.method, path: request.url.pathname },
      requestHash,
      response,
    );
    return response;
  }

  /** The acting user is the assertion's subject; the body never names a user. */
  function actor(request: RouteRequest) {
    return { userId: request.claims.sub, courseId: request.params.courseId ?? '' };
  }

  return [
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces',
      scopes: [WORKSPACE_READ_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        const page = repository.listWorkspaces({
          ...actor(request),
          limit: readLimit(request),
          cursor: request.url.searchParams.get('cursor'),
        });
        return {
          status: 200,
          body: { items: page.items.map(toWorkspace), next_cursor: page.nextCursor },
        };
      }),
    },
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/workspaces',
      scopes: [WORKSPACE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        return withIdempotency(request, body, () => {
          const created = repository.createWorkspace({
            ...actor(request),
            name: requireString(body.name, 'name', 120),
            description: optionalString(body.description, 'description'),
            now: now(),
          });
          return { status: 201, body: toWorkspace(created) };
        });
      }),
    },
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId',
      scopes: [WORKSPACE_READ_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => ({
        status: 200,
        body: toWorkspace(repository.getWorkspace({
          ...actor(request),
          workspaceId: request.params.workspaceId ?? '',
        })),
      })),
    },
    {
      method: 'PATCH',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId',
      scopes: [WORKSPACE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        const updated = repository.updateWorkspace({
          ...actor(request),
          workspaceId: request.params.workspaceId ?? '',
          expectedRevision: requireIfMatch(request),
          patch: {
            name: body.name === undefined ? undefined : requireString(body.name, 'name', 120),
            description: optionalString(body.description, 'description'),
          },
          now: now(),
        });
        return { status: 200, body: toWorkspace(updated) };
      }),
    },
    {
      method: 'DELETE',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId',
      scopes: [WORKSPACE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        repository.softDeleteWorkspace({
          ...actor(request),
          workspaceId: request.params.workspaceId ?? '',
          expectedRevision: requireIfMatch(request),
          now: now(),
        });
        return { status: 200, body: { deleted: true } };
      }),
    },
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages',
      scopes: [WORKSPACE_READ_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        const page = repository.listStages({
          ...actor(request),
          workspaceId: request.params.workspaceId ?? '',
          limit: readLimit(request),
          cursor: request.url.searchParams.get('cursor'),
        });
        return {
          status: 200,
          body: {
            items: page.items.map((row) => toStage(row, { includeDocument: false })),
            next_cursor: page.nextCursor,
          },
        };
      }),
    },
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages',
      scopes: [WORKSPACE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        return withIdempotency(request, body, () => {
          const actorIds = actor(request);
          const workspaceId = request.params.workspaceId ?? '';
          const title = requireString(body.title, 'title', 200);
          // An omitted document means "an empty stage with this title", which is
          // what the workbench asks for before anything has been generated.
          const prepared = prepareStage(
            body.document ?? {
              stage: { id: `stage_${workspaceId}`, name: title, createdAt: Date.now(), updatedAt: Date.now() },
              scenes: [],
            },
          );
          const created = repository.createStage({
            ...actorIds,
            workspaceId,
            title,
            document: prepared.document,
            dslVersion: String((prepared.document as { dslVersion: string }).dslVersion),
            now: now(),
          });
          return { status: 201, body: toStage(created, { includeDocument: true }) };
        });
      }),
    },
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId',
      scopes: [WORKSPACE_READ_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => ({
        status: 200,
        body: toStage(
          repository.getStage({
            ...actor(request),
            workspaceId: request.params.workspaceId ?? '',
            stageId: request.params.stageId ?? '',
          }),
          { includeDocument: true },
        ),
      })),
    },
    {
      method: 'PUT',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId',
      scopes: [WORKSPACE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        if (body.document === undefined) {
          throw new WorkspaceError('invalid_request', 'document is required');
        }
        const prepared = prepareStage(body.document);
        const replaced = repository.replaceStage({
          ...actor(request),
          workspaceId: request.params.workspaceId ?? '',
          stageId: request.params.stageId ?? '',
          expectedRevision: requireIfMatch(request),
          title: optionalString(body.title, 'title', 200),
          document: prepared.document,
          dslVersion: String((prepared.document as { dslVersion: string }).dslVersion),
          now: now(),
        });
        return { status: 200, body: toStage(replaced, { includeDocument: true }) };
      }),
    },
    {
      method: 'DELETE',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId',
      scopes: [WORKSPACE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [WORKSPACE_CAPABILITY],
      handler: (request) => respond(() => {
        repository.softDeleteStage({
          ...actor(request),
          workspaceId: request.params.workspaceId ?? '',
          stageId: request.params.stageId ?? '',
          expectedRevision: requireIfMatch(request),
          now: now(),
        });
        return { status: 200, body: { deleted: true } };
      }),
    },
  ];
}
