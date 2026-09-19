/**
 * Internal `.maic.zip` export + import routes.
 *
 * Both surfaces move one stage in or out of a workspace the caller owns. The
 * rules the gateway relies on:
 *
 * - the acting user is the assertion's `sub` and the course is the path's; every
 *   lookup carries `user_id` + `course_id`, so a foreign stage is a plain 404;
 * - export is read-only and answers the archive as base64 inside the same JSON
 *   envelope every other route uses — the transport has exactly one body shape,
 *   and a second binary path would be a second thing to authenticate;
 * - import is idempotent (`Idempotency-Key`) because a retried upload must not
 *   create the stage twice;
 * - the imported document goes through `prepareStage`, the same migrate →
 *   bound → sanitize → validate path an edited document takes. An archive is not
 *   a way to write a document the editor would refuse.
 */

import type { Capability } from '../capabilities.ts';
import { DslLimitError } from '../dsl/limits.ts';
import { DslVersionError } from '../dsl/version.ts';
import { DslValidationError, prepareStage } from '../dsl/validate.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { WorkspaceRepository, hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER, stageResponse } from '../workspace/routes.ts';
import { exportStage } from './export.ts';
import { decodeArchivePayload, readArchive } from './import.ts';
import { MAIC_FORMAT, MAIC_FORMAT_VERSION } from './manifest.ts';

export const ARCHIVE_READ_SCOPE = 'archive:read';
export const ARCHIVE_WRITE_SCOPE = 'archive:write';
export const EXPORT_MAIC_CAPABILITY: Capability = 'export-maic';
export const IMPORT_MAIC_CAPABILITY: Capability = 'import-maic';

export const MAX_IDEMPOTENCY_KEY_LENGTH = 200;

const FALLBACK_TITLE = '导入的学习内容';

function parseJsonBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body || request.body.length === 0) {
    throw new WorkspaceError('invalid_request', 'request body is required');
  }
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

/** Same translation the editor uses, so a rejected document reads the same way. */
function respond(work: () => RouteResponse): RouteResponse {
  try {
    return work();
  } catch (error) {
    if (error instanceof WorkspaceError) {
      return { status: error.status, body: { error: error.code, message: error.message } };
    }
    if (error instanceof DslLimitError) {
      return { status: 422, body: { error: 'document_rejected', message: error.message, limit: error.limit } };
    }
    if (error instanceof DslValidationError) {
      return { status: 422, body: { error: 'document_rejected', message: error.message, issues: error.issues } };
    }
    if (error instanceof DslVersionError) {
      return { status: 422, body: { error: 'document_rejected', message: error.message } };
    }
    throw error;
  }
}

export interface ArchiveRouteOptions {
  database: ServiceDatabase;
  now?: () => string;
}

export function createArchiveRoutes(options: ArchiveRouteOptions): RouteDefinition[] {
  const repository = new WorkspaceRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  function actor(request: RouteRequest) {
    return {
      userId: request.claims.sub,
      courseId: request.params.courseId ?? '',
      workspaceId: request.params.workspaceId ?? '',
    };
  }

  return [
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/export',
      scopes: [ARCHIVE_READ_SCOPE],
      courseScoped: true,
      capabilities: [EXPORT_MAIC_CAPABILITY],
      handler: (request) => respond(() => {
        const identity = actor(request);
        const stageId = request.params.stageId ?? '';
        // The workspace is read first so its display name can travel in the
        // manifest; both lookups enforce ownership inside the query.
        const workspace = repository.getWorkspace(identity);
        const stage = repository.getStage({ ...identity, stageId });
        const exported = exportStage({
          stage,
          workspaceName: workspace.name,
          exportedAt: now(),
        });
        return {
          status: 200,
          body: {
            format: MAIC_FORMAT,
            format_version: MAIC_FORMAT_VERSION,
            filename: exported.filename,
            stage_title: exported.stageTitle,
            dsl_version: exported.dslVersion,
            byte_size: exported.byteSize,
            sha256: exported.sha256,
            archive: exported.archive.toString('base64'),
          },
        };
      }),
    },
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/import',
      scopes: [ARCHIVE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [IMPORT_MAIC_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
        if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
        if (key.length > MAX_IDEMPOTENCY_KEY_LENGTH) {
          throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');
        }

        const identity = actor(request);
        const userId = request.claims.sub;
        const requestHash = hashRequest({
          method: request.method,
          path: request.url.pathname,
          body,
        });
        const stored = idempotency.lookup(userId, key, requestHash);
        if (stored) return stored;

        // Everything below happens inside the request transaction, so a failure
        // anywhere leaves no half-imported stage behind.
        const parsed = readArchive(decodeArchivePayload(body.archive));
        const prepared = prepareStage(parsed.document);
        const title = parsed.manifest.stage.title.trim() || FALLBACK_TITLE;
        const created = repository.createStage({
          ...identity,
          title,
          document: prepared.document,
          dslVersion: prepared.document.dslVersion,
          now: now(),
        });

        const response: RouteResponse = {
          status: 201,
          body: {
            stage: stageResponse(created, { includeDocument: false }),
            migrated: prepared.migrated,
            // Reported so the caller can say where the file came from. It is
            // display text and never an identity: the landed stage belongs to
            // the caller's workspace regardless of what the archive claims.
            source_workspace_name: parsed.manifest.source.workspace_name,
            format_version: parsed.manifest.format_version,
          },
        };
        idempotency.record(
          userId,
          key,
          { courseId: identity.courseId, method: request.method, path: request.url.pathname },
          requestHash,
          response,
        );
        return response;
      }),
    },
  ];
}
