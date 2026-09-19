/**
 * The `.maic.zip` archive contract.
 *
 * An archive carries **one stage** (the unit a student names and returns to),
 * not a whole workspace: the transport that carries it between the browser and
 * the managed service is JSON with a 4 MiB request cap, and one stage document
 * is bounded at 2 MiB by the DSL. Exporting a workspace would put the archive
 * past that cap on a workspace with two large stages — and a partial export that
 * looks complete is worse than a refused one.
 *
 * The manifest is a *description*, never an identity. It records what the file
 * is and what it came from, for display and provenance. It deliberately does not
 * carry `user_id`, `course_id` or `workspace_id`: an archive is a file a student
 * can share, and nothing in it may decide who owns the import. Where an imported
 * stage lands is decided by the caller's assertion and the path they posted to.
 */

import { DSL_VERSION } from '../dsl/version.ts';
import { WorkspaceError } from '../workspace/errors.ts';

export const MAIC_FORMAT = 'campusmate.maic';
export const MAIC_FORMAT_VERSION = 2;
export const MANIFEST_PATH = 'manifest.json';
export const STAGE_DIRECTORY = 'stages';

/**
 * Bound on the archive itself.
 *
 * Chosen so that the base64 form still fits the transport cap with room for the
 * JSON envelope; `tests/archive.test.mjs` pins that ordering rather than trusting
 * this comment.
 */
export const MAX_ARCHIVE_BYTES = 2.5 * 1024 * 1024;
export const MAX_STAGE_JSON_BYTES = 4 * 1024 * 1024;
export const MAX_SOURCE_NAME_LENGTH = 200;

export interface MaicManifestStage {
  path: string;
  title: string;
  dsl_version: string;
}

export interface MaicManifestResource {
  path: string | null;
  source_id: string;
  filename: string;
  media_type: string;
  byte_size: number;
  sha256: string;
  extraction_status: 'extracted' | 'unsupported' | 'empty';
  text: string;
}

export interface MaicManifest {
  format: string;
  format_version: number;
  exported_at: string;
  dsl_version: string;
  source: { workspace_name: string };
  stage: MaicManifestStage;
  resources: MaicManifestResource[];
}

export interface BuildManifestInput {
  exportedAt: string;
  workspaceName: string;
  title: string;
  dslVersion: string;
  stagePath: string;
  resources?: MaicManifestResource[];
}

export function stagePathFor(stageId: string): string {
  return `${STAGE_DIRECTORY}/${stageId}.json`;
}

export function buildManifest(input: BuildManifestInput): MaicManifest {
  return {
    format: MAIC_FORMAT,
    format_version: MAIC_FORMAT_VERSION,
    exported_at: input.exportedAt,
    dsl_version: input.dslVersion,
    source: { workspace_name: clip(input.workspaceName) },
    stage: {
      path: input.stagePath,
      title: clip(input.title),
      dsl_version: input.dslVersion,
    },
    resources: input.resources ?? [],
  };
}

function clip(value: string): string {
  const text = String(value ?? '').trim();
  return text.length > MAX_SOURCE_NAME_LENGTH ? text.slice(0, MAX_SOURCE_NAME_LENGTH) : text;
}

function reject(message: string): never {
  throw new WorkspaceError('document_rejected', message);
}

/**
 * Validate a manifest read out of an archive.
 *
 * An unknown `format_version` is refused rather than best-effort parsed: a future
 * archive may carry meaning this build cannot represent, and importing part of it
 * would silently drop that meaning. `dsl_version` is reported but not enforced
 * here — the stage document goes through `prepareStage`, which is the one place
 * that knows how to migrate an older document.
 */
export function parseManifest(raw: unknown): MaicManifest {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    reject('manifest is not a JSON object');
  }
  const value = raw as Record<string, unknown>;
  if (value.format !== MAIC_FORMAT) {
    reject(`archive is not a ${MAIC_FORMAT} archive`);
  }
  const version = value.format_version;
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    reject('manifest format_version is missing or malformed');
  }
  if (version > MAIC_FORMAT_VERSION) {
    reject(`archive format_version ${version} is newer than this build supports (${MAIC_FORMAT_VERSION})`);
  }
  const stage = value.stage;
  if (typeof stage !== 'object' || stage === null || Array.isArray(stage)) {
    reject('manifest is missing its stage record');
  }
  const stageRecord = stage as Record<string, unknown>;
  if (typeof stageRecord.path !== 'string' || stageRecord.path.length === 0) {
    reject('manifest stage record is missing its path');
  }
  if (typeof stageRecord.title !== 'string') {
    reject('manifest stage record is missing its title');
  }
  const dslVersion = typeof stageRecord.dsl_version === 'string' ? stageRecord.dsl_version : '';
  const source = value.source;
  const workspaceName =
    typeof source === 'object' && source !== null && typeof (source as Record<string, unknown>).workspace_name === 'string'
      ? ((source as Record<string, unknown>).workspace_name as string)
      : '';
  const resources = parseResources(value.resources);
  return {
    format: MAIC_FORMAT,
    format_version: version,
    exported_at: typeof value.exported_at === 'string' ? value.exported_at : '',
    dsl_version: dslVersion || DSL_VERSION,
    source: { workspace_name: workspaceName },
    stage: { path: stageRecord.path, title: stageRecord.title, dsl_version: dslVersion || DSL_VERSION },
    resources,
  };
}

function parseResources(raw: unknown): MaicManifestResource[] {
  if (raw === undefined) return [];
  if (!Array.isArray(raw) || raw.length > 50) reject('manifest resources are malformed or too numerous');
  const seen = new Set<string>();
  const paths = new Set<string>();
  return raw.map((entry, index) => {
    if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) {
      reject(`manifest resource ${index} is not an object`);
    }
    const resource = entry as Record<string, unknown>;
    const sourceId = resource.source_id;
    const filename = resource.filename;
    const mediaType = resource.media_type;
    const sha256 = resource.sha256;
    const status = resource.extraction_status;
    const text = resource.text;
    const path = resource.path;
    if (typeof sourceId !== 'string' || sourceId.length < 1 || sourceId.length > 200 || seen.has(sourceId)) {
      reject(`manifest resource ${index} has an invalid source_id`);
    }
    if (typeof filename !== 'string' || filename.length < 1 || filename.length > 255 || /[\\/\u0000-\u001f]/.test(filename)) {
      reject(`manifest resource ${index} has an invalid filename`);
    }
    if (typeof mediaType !== 'string' || mediaType.length < 1 || mediaType.length > 200) {
      reject(`manifest resource ${index} has an invalid media_type`);
    }
    if (typeof sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(sha256)) reject(`manifest resource ${index} has an invalid sha256`);
    if (typeof status !== 'string' || !['extracted', 'unsupported', 'empty'].includes(status)) {
      reject(`manifest resource ${index} has an invalid extraction_status`);
    }
    if (typeof text !== 'string' || Buffer.byteLength(text, 'utf8') > 512 * 1024) {
      reject(`manifest resource ${index} has invalid text`);
    }
    if (status === 'extracted' && (text as string).length === 0) reject(`manifest resource ${index} has no extracted text`);
    if (status !== 'extracted' && (text as string).length > 0) reject(`manifest resource ${index} has text for an unsupported extraction`);
    if (typeof resource.byte_size !== 'number' || !Number.isInteger(resource.byte_size) || resource.byte_size < 0 || resource.byte_size > 2 * 1024 * 1024) {
      reject(`manifest resource ${index} has an invalid byte_size`);
    }
    if (path !== null && (typeof path !== 'string' || !path.startsWith('resources/') || paths.has(path))) {
      reject(`manifest resource ${index} has an invalid path`);
    }
    seen.add(sourceId);
    if (typeof path === 'string') paths.add(path);
    return {
      path: path as string | null,
      source_id: sourceId,
      filename,
      media_type: mediaType,
      byte_size: resource.byte_size,
      sha256,
      extraction_status: status as MaicManifestResource['extraction_status'],
      text,
    };
  });
}

/** A filename a browser can save without a path separator or a reserved name. */
export function archiveFilename(title: string): string {
  const cleaned = String(title ?? '')
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, ' ')
    .trim()
    .slice(0, 80);
  return `${cleaned || '学习内容'}.maic.zip`;
}
