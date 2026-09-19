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
export const MAIC_FORMAT_VERSION = 1;
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

export interface MaicManifest {
  format: string;
  format_version: number;
  exported_at: string;
  dsl_version: string;
  source: { workspace_name: string };
  stage: MaicManifestStage;
}

export interface BuildManifestInput {
  exportedAt: string;
  workspaceName: string;
  title: string;
  dslVersion: string;
  stagePath: string;
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
  return {
    format: MAIC_FORMAT,
    format_version: version,
    exported_at: typeof value.exported_at === 'string' ? value.exported_at : '',
    dsl_version: dslVersion || DSL_VERSION,
    source: { workspace_name: workspaceName },
    stage: { path: stageRecord.path, title: stageRecord.title, dsl_version: dslVersion || DSL_VERSION },
  };
}

/** A filename a browser can save without a path separator or a reserved name. */
export function archiveFilename(title: string): string {
  const cleaned = String(title ?? '')
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, ' ')
    .trim()
    .slice(0, 80);
  return `${cleaned || '学习内容'}.maic.zip`;
}
