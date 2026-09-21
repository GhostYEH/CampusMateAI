/**
 * Internal folder + search routes.
 *
 * Both surfaces are navigation over a student's own content, so the rules the
 * gateway relies on are enforced here:
 *
 * - the acting user is always the assertion's `sub`; no request body may name
 *   one, and every query carries `user_id` + `course_id`;
 * - creating a folder is idempotent (retrying a flaky create must not clone the
 *   tree) and renaming/deleting is conditional on `If-Match`;
 * - a keyword search answers `400` for an empty or overlong query instead of
 *   quietly returning the whole course, because "no query" is a mistake, not a
 *   request for everything.
 */

import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER, IF_MATCH_HEADER } from '../workspace/routes.ts';
import {
  DiscoveryRepository,
  MAX_QUERY_LENGTH,
  stageDeepLink,
  type FolderListItem,
  type FolderRow,
  type SearchHit,
} from './repository.ts';

export const FOLDER_READ_SCOPE = 'folder:read';
export const FOLDER_WRITE_SCOPE = 'folder:write';
export const SEARCH_READ_SCOPE = 'search:read';
export const FOLDER_CAPABILITY: Capability = 'folder';
export const SEARCH_CAPABILITY: Capability = 'search';

function toFolder(row: FolderRow, workspaceCount?: number): Record<string, unknown> {
  const body: Record<string, unknown> = {
    id: row.id,
    course_id: row.course_id,
    parent_id: row.parent_id,
    name: row.name,
    revision: Number(row.revision),
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
  if (workspaceCount !== undefined) body.workspace_count = workspaceCount;
  return body;
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

/** `null` is a meaningful value here ("move to the root"), so it is not `undefined`. */
function optionalNullableId(value: unknown, field: string): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new WorkspaceError('invalid_request', `${field} must be a non-empty string or null`);
  }
  return value.trim();
}

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

function readQuery(request: RouteRequest): string {
  const raw = request.url.searchParams.get('q');
  if (raw === null) throw new WorkspaceError('invalid_request', 'q is required');
  const query = raw.trim();
  if (query.length === 0) throw new WorkspaceError('invalid_request', 'q must not be blank');
  if (query.length > MAX_QUERY_LENGTH) {
    throw new WorkspaceError('invalid_request', `q must be at most ${MAX_QUERY_LENGTH} characters`);
  }
  return query;
}

function toSearchHit(hit: SearchHit, courseId: string): Record<string, unknown> {
  return {
    kind: hit.kind,
    workspace_id: hit.workspace_id,
    stage_id: hit.stage_id,
    title: hit.title,
    snippet: hit.snippet,
    folder_id: hit.folder_id,
    updated_at: hit.updated_at,
    path: stageDeepLink(courseId, hit.workspace_id, hit.stage_id),
  };
}

function respond(work: () => RouteResponse): RouteResponse {
  try {
    return work();
  } catch (error) {
    if (error instanceof WorkspaceError) {
      return { status: error.status, body: { error: error.code, message: error.message } };
    }
    throw error;
  }
}

export interface DiscoveryRouteOptions {
  database: ServiceDatabase;
  now?: () => string;
}

export function createDiscoveryRoutes(options: DiscoveryRouteOptions): RouteDefinition[] {
  const repository = new DiscoveryRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  function actor(request: RouteRequest) {
    return { userId: request.claims.sub, courseId: request.params.courseId ?? '' };
  }

  /**
   * Idempotent create. The route is part of the digest so the same key used on a
   * different path with a coincidentally identical body cannot replay the wrong
   * response.
   */
  function withIdempotency(
    request: RouteRequest,
    body: unknown,
    work: () => RouteResponse,
  ): RouteResponse {
    const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
    if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
    if (key.length > 200) throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');
    const userId = request.claims.sub;
    const requestHash = hashRequest({
      method: request.method,
      path: request.url.pathname,
      body: body ?? null,
    });
    const stored = idempotency.lookup(userId, key, requestHash);
    if (stored) return stored;
    const response = work();
    idempotency.record(
      userId,
      key,
      { courseId: request.params.courseId ?? '', method: request.method, path: request.url.pathname },
      requestHash,
      response,
    );
    return response;
  }

  return [
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/folders',
      scopes: [FOLDER_READ_SCOPE],
      courseScoped: true,
      capabilities: [FOLDER_CAPABILITY],
      handler: (request) => respond(() => {
        const page = repository.listFolders({
          ...actor(request),
          limit: readLimit(request),
          cursor: request.url.searchParams.get('cursor'),
        });
        return {
          status: 200,
          body: {
            items: page.items.map((item: FolderListItem) => toFolder(item, Number(item.workspace_count))),
            next_cursor: page.nextCursor,
          },
        };
      }),
    },
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/folders',
      scopes: [FOLDER_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [FOLDER_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        return withIdempotency(request, body, () => {
          const created = repository.createFolder({
            ...actor(request),
            name: requireString(body.name, 'name', 120),
            parentId: optionalNullableId(body.parent_id, 'parent_id') ?? null,
            now: now(),
          });
          return { status: 201, body: toFolder(created) };
        });
      }),
    },
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/folders/:folderId',
      scopes: [FOLDER_READ_SCOPE],
      courseScoped: true,
      capabilities: [FOLDER_CAPABILITY],
      handler: (request) => respond(() => ({
        status: 200,
        body: toFolder(repository.getFolder({
          ...actor(request),
          folderId: request.params.folderId ?? '',
        })),
      })),
    },
    {
      method: 'PATCH',
      pattern: '/internal/courses/:courseId/folders/:folderId',
      scopes: [FOLDER_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [FOLDER_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        const updated = repository.updateFolder({
          ...actor(request),
          folderId: request.params.folderId ?? '',
          expectedRevision: requireIfMatch(request),
          patch: {
            name: body.name === undefined ? undefined : requireString(body.name, 'name', 120),
            parentId: optionalNullableId(body.parent_id, 'parent_id'),
          },
          now: now(),
        });
        return { status: 200, body: toFolder(updated) };
      }),
    },
    {
      method: 'DELETE',
      pattern: '/internal/courses/:courseId/folders/:folderId',
      scopes: [FOLDER_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [FOLDER_CAPABILITY],
      handler: (request) => respond(() => {
        repository.softDeleteFolder({
          ...actor(request),
          folderId: request.params.folderId ?? '',
          expectedRevision: requireIfMatch(request),
          now: now(),
        });
        return { status: 200, body: { deleted: true } };
      }),
    },
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/search',
      scopes: [SEARCH_READ_SCOPE],
      courseScoped: true,
      capabilities: [SEARCH_CAPABILITY],
      handler: (request) => respond(() => {
        const courseId = request.params.courseId ?? '';
        const page = repository.search({
          ...actor(request),
          query: readQuery(request),
          limit: readLimit(request),
          cursor: request.url.searchParams.get('cursor'),
        });
        return {
          status: 200,
          body: {
            items: page.items.map((hit) => toSearchHit(hit, courseId)),
            next_cursor: page.nextCursor,
          },
        };
      }),
    },
  ];
}
