/**
 * Internal stage-editing route.
 *
 * The editor is the one surface where a client and the service both hold a
 * document, so the rules are deliberately strict:
 *
 * - **the client sends commands, not a document.** A whole-document PUT lets an
 *   author who never saw a concurrent change overwrite it; a command list is
 *   applied to the row the service just read, inside the request transaction;
 * - **a conditional write must carry `If-Match`** — the same convention the
 *   workspace routes use, so the same conflict semantics reach the browser;
 * - **a retryable write must carry an `Idempotency-Key`.** Applying the same
 *   command twice creates two scenes; the stored response is replayed instead;
 * - **the DSL ladder still owns the result.** Commands produce an aggregate that
 *   is then migrated, sanitized and validated, so a command can never persist a
 *   document the player would refuse.
 */

import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import {
  DslCommandError,
  DslLimitError,
  DslValidationError,
  DslVersionError,
  applyStageCommands,
  prepareStage,
} from '../dsl/index.ts';
import type { StageAggregate } from '../dsl/contract.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError, notFound } from '../workspace/errors.ts';
import { WorkspaceRepository, hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER, IF_MATCH_HEADER, stageResponse } from '../workspace/routes.ts';

export const STAGE_READ_SCOPE = 'stage:read';
export const STAGE_WRITE_SCOPE = 'stage:write';
export const EDITOR_CAPABILITY: Capability = 'editor';

const MAX_COMMANDS_PER_REQUEST = 50;

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

/**
 * Map every expected failure onto its own status.
 *
 * A rejected command is `422` (the document the client asked for cannot exist),
 * which mirrors how the DSL write path already answers an invalid document; the
 * gateway reduces the payload to what the client can act on.
 */
function respond(work: () => RouteResponse): RouteResponse {
  try {
    return work();
  } catch (error) {
    if (error instanceof WorkspaceError) {
      return { status: error.status, body: { error: error.code, message: error.message } };
    }
    if (error instanceof DslCommandError) {
      return {
        status: 422,
        body: { error: 'command_rejected', code: error.code, path: error.path, message: error.message },
      };
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

export interface EditorRouteOptions {
  database: ServiceDatabase;
  now?: () => string;
}

export function createEditorRoutes(options: EditorRouteOptions): RouteDefinition[] {
  const repository = new WorkspaceRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  function actor(request: RouteRequest) {
    return {
      userId: request.claims.sub,
      courseId: request.params.courseId ?? '',
      workspaceId: request.params.workspaceId ?? '',
      stageId: request.params.stageId ?? '',
    };
  }

  return [
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/commands',
      scopes: [STAGE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [EDITOR_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
        if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
        if (key.length > 200) throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');

        const expectedRevision = requireIfMatch(request);
        const identity = actor(request);
        const userId = request.claims.sub;
        const requestHash = hashRequest({
          method: request.method,
          path: request.url.pathname,
          body,
        });

        const replay = idempotency.lookup(userId, key, requestHash);
        if (replay) return replay;

        // The stage must exist and belong to this caller before anything is
        // applied, so a foreign id cannot be probed by observing a validation
        // error instead of a 404.
        const current = repository.getStage(identity);
        const commands = body.commands;
        if (!Array.isArray(commands)) {
          throw new WorkspaceError('invalid_request', 'commands must be an array');
        }
        if (commands.length === 0) {
          throw new WorkspaceError('invalid_request', 'commands must not be empty');
        }
        if (commands.length > MAX_COMMANDS_PER_REQUEST) {
          throw new WorkspaceError('invalid_request', `commands must not exceed ${MAX_COMMANDS_PER_REQUEST} items`);
        }

        const aggregate = JSON.parse(current.document) as StageAggregate;
        const applied = applyStageCommands(aggregate, commands);
        const prepared = prepareStage(applied);
        const replaced = repository.replaceStage({
          ...identity,
          expectedRevision,
          document: prepared.document,
          dslVersion: String((prepared.document as { dslVersion: string }).dslVersion),
          now: now(),
        });

        const response: RouteResponse = {
          status: 200,
          body: {
            ...stageResponse(replaced, { includeDocument: true }),
            applied_commands: commands.length,
            migrated: prepared.migrated,
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
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/outline',
      scopes: [STAGE_READ_SCOPE],
      courseScoped: true,
      capabilities: [EDITOR_CAPABILITY],
      handler: (request) => respond(() => {
        const row = repository.getStage(actor(request));
        const aggregate = JSON.parse(row.document) as StageAggregate;
        return {
          status: 200,
          body: {
            stage_id: row.id,
            workspace_id: row.workspace_id,
            title: row.title,
            revision: Number(row.revision),
            dsl_version: row.dsl_version,
            // The outline deliberately omits scene content: it is what the scene
            // list renders, and shipping every slide to draw a sidebar is how a
            // navigation panel becomes the slowest part of the editor.
            scenes: aggregate.scenes.map((scene) => ({
              id: scene.id,
              type: scene.type,
              title: scene.title,
              order: scene.order,
              actions: Array.isArray(scene.actions) ? scene.actions.length : 0,
              updated_at: scene.updatedAt ?? null,
            })),
          },
        };
      }),
    },
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/scenes/:sceneId',
      scopes: [STAGE_READ_SCOPE],
      courseScoped: true,
      capabilities: [EDITOR_CAPABILITY],
      handler: (request) => respond(() => {
        const row = repository.getStage(actor(request));
        const aggregate = JSON.parse(row.document) as StageAggregate;
        const sceneId = request.params.sceneId ?? '';
        const scene = aggregate.scenes.find((item) => item.id === sceneId);
        if (!scene) notFound();
        return { status: 200, body: scene };
      }),
    },
  ];
}
