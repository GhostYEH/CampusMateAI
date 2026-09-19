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
import { createHash } from 'node:crypto';
import { DslLimitError } from '../dsl/limits.ts';
import { DslVersionError } from '../dsl/version.ts';
import { DslValidationError, prepareStage } from '../dsl/validate.ts';
import type { ServiceDatabase } from '../db/database.ts';
import type { RenderConfig } from '../config.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { WorkspaceRepository, hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER, stageResponse } from '../workspace/routes.ts';
import { exportStage } from './export.ts';
import { decodeArchivePayload, readArchive } from './import.ts';
import { MAIC_FORMAT, MAIC_FORMAT_VERSION } from './manifest.ts';
import { exportDocx } from '../exporters/docx.ts';
import { exportMarkdown } from '../exporters/markdown.ts';
import { exportPptx } from '../exporters/pptx.ts';
import { importPptx } from '../importers/pptx.ts';
import { JobRepository } from '../jobs/repository.ts';
import { jobResponse } from '../jobs/routes.ts';
import { MaterialRepository } from '../material/repository.ts';

export const ARCHIVE_READ_SCOPE = 'archive:read';
export const ARCHIVE_WRITE_SCOPE = 'archive:write';
export const EXPORT_MAIC_CAPABILITY: Capability = 'export-maic';
export const IMPORT_MAIC_CAPABILITY: Capability = 'import-maic';
export const EXPORT_PPTX_CAPABILITY: Capability = 'export-pptx';
export const EXPORT_MARKDOWN_CAPABILITY: Capability = 'export-markdown';
export const EXPORT_DOCX_CAPABILITY: Capability = 'export-docx';
export const IMPORT_PPTX_CAPABILITY: Capability = 'import-pptx';
export const EXPORT_VIDEO_CAPABILITY: Capability = 'export-video';

export const MAX_IDEMPOTENCY_KEY_LENGTH = 200;

const FALLBACK_TITLE = '导入的学习内容';

const MAX_ARCHIVE_MATERIALS = 50;

function materialIdsInDocument(document: unknown): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  const visit = (value: unknown) => {
    if (Array.isArray(value)) {
      for (const item of value) visit(item);
      return;
    }
    if (typeof value !== 'object' || value === null) return;
    for (const [key, child] of Object.entries(value)) {
      if (key === 'material_id') {
        if (typeof child !== 'string' || !child.trim()) {
          throw new WorkspaceError('document_rejected', 'material_id must be a non-empty string');
        }
        if (!seen.has(child)) { seen.add(child); ids.push(child); }
      } else if (key === 'material_ids' && Array.isArray(child)) {
        for (const item of child) {
          if (typeof item !== 'string' || !item.trim()) {
            throw new WorkspaceError('document_rejected', 'material_ids must hold non-empty strings');
          }
          if (!seen.has(item)) { seen.add(item); ids.push(item); }
        }
      } else if (key === 'material_ids') {
        throw new WorkspaceError('document_rejected', 'material_ids must be a list');
      }
      visit(child);
    }
  };
  visit(document);
  if (ids.length > MAX_ARCHIVE_MATERIALS) {
    throw new WorkspaceError('document_rejected', `stage references more than ${MAX_ARCHIVE_MATERIALS} materials`);
  }
  return ids;
}

function remapMaterialIds(value: unknown, mapping: Map<string, string>): unknown {
  if (Array.isArray(value)) return value.map((item) => remapMaterialIds(item, mapping));
  if (typeof value !== 'object' || value === null) return value;
  const output: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(value)) {
    if (key === 'material_id' && typeof child === 'string') output[key] = mapping.get(child) ?? child;
    else if (key === 'material_ids' && Array.isArray(child)) output[key] = child.map((item) => typeof item === 'string' ? (mapping.get(item) ?? item) : item);
    else output[key] = remapMaterialIds(child, mapping);
  }
  return output;
}

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

function decodeBinaryBody(value: unknown, field: string): Buffer {
  if (typeof value !== 'string' || value.length === 0 || value.length > 6_000_000) {
    throw new WorkspaceError('invalid_request', `${field} must be a bounded base64 string`);
  }
  let decoded: Buffer;
  try {
    decoded = Buffer.from(value, 'base64');
  } catch {
    throw new WorkspaceError('invalid_request', `${field} is not valid base64`);
  }
  if (decoded.length === 0 || decoded.toString('base64') !== value.replace(/\s/g, '')) {
    throw new WorkspaceError('invalid_request', `${field} is not valid base64`);
  }
  return decoded;
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
  jobs?: JobRepository;
  render?: RenderConfig;
}

export function createArchiveRoutes(options: ArchiveRouteOptions): RouteDefinition[] {
  const repository = new WorkspaceRepository(options.database);
  const materials = new MaterialRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  function actor(request: RouteRequest) {
    return {
      userId: request.claims.sub,
      courseId: request.params.courseId ?? '',
      workspaceId: request.params.workspaceId ?? '',
    };
  }

  const routes: RouteDefinition[] = [
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
        let document: unknown;
        try { document = JSON.parse(stage.document); } catch { throw new WorkspaceError('document_rejected', 'stored stage document is not valid JSON'); }
        const stageMaterials = materialIdsInDocument(document).map((materialId) => materials.getMaterialForArchive({
          userId: identity.userId,
          courseId: identity.courseId,
          materialId,
        }));
        const exported = exportStage({
          stage,
          workspaceName: workspace.name,
          exportedAt: now(),
          materials: stageMaterials,
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
    ...[
      ['markdown', EXPORT_MARKDOWN_CAPABILITY, exportMarkdown],
      ['docx', EXPORT_DOCX_CAPABILITY, exportDocx],
      ['pptx', EXPORT_PPTX_CAPABILITY, exportPptx],
    ].map(([format, capability, exporter]) => ({
      method: 'GET' as const,
      pattern: `/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/export/${format}`,
      scopes: [ARCHIVE_READ_SCOPE],
      courseScoped: true,
      capabilities: [capability as Capability],
      handler: (request: RouteRequest) => respond(() => {
        const identity = actor(request);
        const workspace = repository.getWorkspace(identity);
        const stage = repository.getStage({ ...identity, stageId: request.params.stageId ?? '' });
        const exported = (exporter as (input: { stage: typeof stage; exportedAt: string }) => ReturnType<typeof exportMarkdown>)({
          stage,
          exportedAt: now(),
        });
        return {
          status: 200,
          body: {
            format,
            filename: exported.filename,
            stage_title: exported.stageTitle,
            byte_size: exported.byteSize,
            sha256: exported.sha256,
            media_type: exported.mediaType,
            workspace_name: workspace.name,
            content: exported.content.toString('base64'),
          },
        };
      }),
    })),
    {
      method: 'POST',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/import/pptx',
      scopes: [ARCHIVE_WRITE_SCOPE],
      courseScoped: true,
      capabilities: [IMPORT_PPTX_CAPABILITY],
      handler: (request) => respond(() => {
        const body = parseJsonBody(request);
        const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
        if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
        if (key.length > MAX_IDEMPOTENCY_KEY_LENGTH) throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');
        const identity = actor(request);
        const userId = request.claims.sub;
        const requestHash = hashRequest({ method: request.method, path: request.url.pathname, body });
        const stored = idempotency.lookup(userId, key, requestHash);
        if (stored) return stored;
        const imported = importPptx(decodeBinaryBody(body.pptx, 'pptx'), {
          title: typeof body.title === 'string' ? body.title : '导入的课件',
        });
        const prepared = prepareStage(imported);
        const created = repository.createStage({
          ...identity,
          title: prepared.document.stage.name,
          document: prepared.document,
          dslVersion: prepared.document.dslVersion,
          now: now(),
        });
        const response: RouteResponse = {
          status: 201,
          body: { stage: stageResponse(created, { includeDocument: false }), migrated: prepared.migrated, format: 'pptx' },
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
        const materialMapping = new Map<string, string>();
        for (const resource of parsed.resources) {
          if (resource.payload && createHash('sha256').update(resource.payload).digest('hex') !== resource.manifest.sha256) {
            throw new WorkspaceError('document_rejected', `resource ${resource.manifest.filename} failed its integrity check`);
          }
          const createdMaterial = materials.createMaterial({
            userId: identity.userId,
            courseId: identity.courseId,
            filename: resource.manifest.filename,
            mediaType: resource.manifest.media_type,
            byteSize: resource.manifest.byte_size,
            sha256: resource.manifest.sha256,
            extractionStatus: resource.manifest.extraction_status,
            text: resource.manifest.text,
            payload: resource.payload ?? undefined,
            now: now(),
          });
          materialMapping.set(resource.manifest.source_id, createdMaterial.material.id);
        }
        for (const materialId of materialIdsInDocument(parsed.document)) {
          if (!materialMapping.has(materialId)) {
            throw new WorkspaceError('document_rejected', `archive is missing material resource ${materialId}`);
          }
        }
        const prepared = prepareStage(remapMaterialIds(parsed.document, materialMapping));
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

  if (options.jobs && options.render) {
    routes.push({
      method: 'POST',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/export/video',
      scopes: [ARCHIVE_READ_SCOPE, 'job:write'],
      courseScoped: true,
      capabilities: [EXPORT_VIDEO_CAPABILITY],
      handler: (request) => respond(() => {
        const identity = actor(request);
        const stage = repository.getStage({ ...identity, stageId: request.params.stageId ?? '' });
        const userId = request.claims.sub;
        const body = { workspace_id: identity.workspaceId, stage_id: stage.id, format: 'mp4' };
        const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
        if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
        if (key.length > MAX_IDEMPOTENCY_KEY_LENGTH) throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');
        const requestHash = hashRequest({ method: request.method, path: request.url.pathname, body });
        const stored = idempotency.lookup(userId, key, requestHash);
        if (stored) return stored;
        const row = options.jobs!.create({ userId, courseId: identity.courseId, kind: 'video', mode: 'mp4', request: body, now: now() });
        const response: RouteResponse = { status: 202, body: { job_id: row.id, job: jobResponse(row), format: 'mp4', source: 'render-service' } };
        idempotency.record(userId, key, { courseId: identity.courseId, method: request.method, path: request.url.pathname }, requestHash, response);
        return response;
      }),
    });
  }
  return routes;
}
