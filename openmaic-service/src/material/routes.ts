/**
 * Internal material routes.
 *
 * A material is the one surface where the service stores text taken from a file
 * the student chose, so the rules the gateway relies on are enforced here rather
 * than trusted from upstream:
 *
 * - the acting user is always the assertion's `sub`, every query carries
 *   `user_id` + `course_id`, and a foreign id is a plain 404;
 * - an upload is idempotent (a retry must not clone the material) and carries a
 *   digest, so the same bytes are the same material;
 * - a delete is conditional on `If-Match`;
 * - a payload that cannot be honest is refused by name: a size above
 *   `MAX_MATERIAL_BYTES`, a digest that is not a sha256, or an `unsupported`
 *   extraction that carries text all become `document_rejected` / `invalid_request`
 *   instead of being stored and later presented as real content.
 *
 * Route order matters: `POST .../materials/resolve` is registered before
 * `GET|DELETE .../materials/:materialId`, because both patterns have the same
 * shape. Material ids are `mt_`-prefixed, so `resolve` is not a reachable id —
 * and a test pins that the ordering holds.
 */

import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER, IF_MATCH_HEADER } from '../workspace/routes.ts';
import {
  EXTRACTION_STATUSES,
  MAX_FILENAME_LENGTH,
  MAX_MATERIAL_BYTES,
  MAX_MATERIAL_TEXT_BYTES,
  MAX_MEDIA_TYPE_LENGTH,
  MAX_REFERENCE_COUNT,
  MaterialRepository,
  type ExtractionStatus,
  type MaterialRecord,
  type MaterialSummary,
} from './repository.ts';

export { MAX_MATERIAL_BYTES, MAX_MATERIAL_TEXT_BYTES, MAX_REFERENCE_COUNT } from './repository.ts';

export const MATERIAL_READ_SCOPE = 'material:read';
export const MATERIAL_WRITE_SCOPE = 'material:write';
export const MATERIAL_CAPABILITY: Capability = 'material';

/** Every character that would make a filename mean "somewhere else on disk". */
const PATH_SEPARATORS = /[/\\]/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

function summaryToJson(row: MaterialSummary): Record<string, unknown> {
  return {
    id: row.id,
    course_id: row.course_id,
    filename: row.filename,
    media_type: row.media_type,
    byte_size: Number(row.byte_size),
    sha256: row.sha256,
    extraction_status: row.extraction_status,
    text_chars: Number(row.text_chars),
    revision: Number(row.revision),
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function recordToJson(row: MaterialRecord): Record<string, unknown> {
  return {
    id: row.id,
    course_id: row.course_id,
    filename: row.filename,
    media_type: row.media_type,
    byte_size: Number(row.byte_size),
    sha256: row.sha256,
    extraction_status: row.extraction_status,
    text: row.text,
    text_chars: row.text.length,
    revision: Number(row.revision),
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
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

function requireString(value: unknown, field: string, maxLength: number): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new WorkspaceError('invalid_request', `${field} is required`);
  }
  const trimmed = value.trim();
  if (trimmed.length > maxLength) {
    throw new WorkspaceError('invalid_request', `${field} is too long`);
  }
  return trimmed;
}

function requireFilename(value: unknown): string {
  const filename = requireString(value, 'filename', MAX_FILENAME_LENGTH);
  if (PATH_SEPARATORS.test(filename)) {
    throw new WorkspaceError('invalid_request', 'filename must not contain a path separator');
  }
  return filename;
}

function requireByteSize(value: unknown): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) {
    throw new WorkspaceError('invalid_request', 'byte_size must be a non-negative integer');
  }
  if (value > MAX_MATERIAL_BYTES) {
    // Named rather than truncated: a material that silently lost its tail would
    // be cited later as if it were complete.
    throw new WorkspaceError('document_rejected', `byte_size must be at most ${MAX_MATERIAL_BYTES}`);
  }
  return value;
}

function requireSha256(value: unknown): string {
  if (typeof value !== 'string' || !SHA256_PATTERN.test(value)) {
    throw new WorkspaceError('invalid_request', 'sha256 must be 64 lowercase hex characters');
  }
  return value;
}

function requireExtractionStatus(value: unknown): ExtractionStatus {
  if (typeof value !== 'string' || !EXTRACTION_STATUSES.includes(value as ExtractionStatus)) {
    throw new WorkspaceError(
      'invalid_request',
      `extraction_status must be one of ${EXTRACTION_STATUSES.join(', ')}`,
    );
  }
  return value as ExtractionStatus;
}

/**
 * The text must match the status that describes it.
 *
 * `unsupported` carrying text is the one combination that would turn a parser
 * failure into fabricated course content, so it is refused rather than ignored.
 */
function requireText(value: unknown, status: ExtractionStatus): string {
  const text = value === undefined || value === null ? '' : value;
  if (typeof text !== 'string') {
    throw new WorkspaceError('invalid_request', 'text must be a string');
  }
  if (Buffer.byteLength(text, 'utf8') > MAX_MATERIAL_TEXT_BYTES) {
    throw new WorkspaceError('document_rejected', `text must be at most ${MAX_MATERIAL_TEXT_BYTES} bytes`);
  }
  if (status === 'extracted' && text.length === 0) {
    throw new WorkspaceError('document_rejected', 'an extracted material must carry its text');
  }
  if (status !== 'extracted' && text.length > 0) {
    throw new WorkspaceError('document_rejected', `a ${status} material must not carry text`);
  }
  return text;
}

function requireMaterialIds(value: unknown): string[] {
  if (!Array.isArray(value)) {
    throw new WorkspaceError('invalid_request', 'material_ids must be a list');
  }
  if (value.length > MAX_REFERENCE_COUNT) {
    throw new WorkspaceError('invalid_request', `material_ids must hold at most ${MAX_REFERENCE_COUNT} entries`);
  }
  return value.map((entry) => {
    if (typeof entry !== 'string' || entry.trim().length === 0) {
      throw new WorkspaceError('invalid_request', 'material_ids must hold non-empty strings');
    }
    return entry.trim();
  });
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

export interface MaterialRouteOptions {
  database: ServiceDatabase;
  now?: () => string;
}

export function createMaterialRoutes(options: MaterialRouteOptions): RouteDefinition[] {
  const repository = new MaterialRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  function actor(request: RouteRequest) {
    return { userId: request.claims.sub, courseId: request.params.courseId ?? '' };
  }

  function withIdempotency(request: RouteRequest, body: unknown, work: () => RouteResponse): RouteResponse {
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
      pattern: '/internal/courses/:courseId/materials',
      scopes: [MATERIAL_READ_SCOPE],
      courseScoped: true,
      capabilities: [MATERIAL_CAPABILITY],
      handler: (request) => respond(() => {
        const page = repository.listMaterials({
          ...actor(request),
          limit: readLimit(request),
          cursor: request.url.searchParams.get('cursor'),
        });
        return {
          status: 200,
          body: { items: page.items.map(summaryToJson), next_cursor: page.nextCursor },
        };
      }),
    },
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/materials',
      scopes: [MATERIAL_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [MATERIAL_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        return withIdempotency(request, body, () => {
          const extractionStatus = requireExtractionStatus(body.extraction_status);
          const created = repository.createMaterial({
            ...actor(request),
            filename: requireFilename(body.filename),
            mediaType: requireString(body.media_type, 'media_type', MAX_MEDIA_TYPE_LENGTH),
            byteSize: requireByteSize(body.byte_size),
            sha256: requireSha256(body.sha256),
            extractionStatus,
            text: requireText(body.text, extractionStatus),
            now: now(),
          });
          return {
            status: 201,
            body: { ...summaryToJson(created.material), deduplicated: created.deduplicated },
          };
        });
      }),
    },
    // Registered before `/materials/:materialId`; see the module comment.
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/materials/resolve',
      scopes: [MATERIAL_READ_SCOPE],
      courseScoped: true,
      capabilities: [MATERIAL_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        const resolution = repository.resolveReferences({
          ...actor(request),
          materialIds: requireMaterialIds(body.material_ids),
        });
        return {
          status: 200,
          body: {
            resolved: resolution.resolved.map((row) => ({
              id: row.id,
              filename: row.filename,
              media_type: row.media_type,
              extraction_status: row.extraction_status,
              text_chars: Number(row.text_chars),
              updated_at: row.updated_at,
            })),
            unresolved: resolution.unresolved,
          },
        };
      }),
    },
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/materials/:materialId',
      scopes: [MATERIAL_READ_SCOPE],
      courseScoped: true,
      capabilities: [MATERIAL_CAPABILITY],
      handler: (request) => respond(() => ({
        status: 200,
        body: recordToJson(
          repository.getMaterial({ ...actor(request), materialId: request.params.materialId ?? '' }),
        ),
      })),
    },
    {
      method: 'DELETE',
      pattern: '/internal/courses/:courseId/materials/:materialId',
      scopes: [MATERIAL_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [MATERIAL_CAPABILITY],
      handler: (request) => respond(() => {
        repository.softDeleteMaterial({
          ...actor(request),
          materialId: request.params.materialId ?? '',
          expectedRevision: requireIfMatch(request),
          now: now(),
        });
        return { status: 200, body: { deleted: true } };
      }),
    },
  ];
}
