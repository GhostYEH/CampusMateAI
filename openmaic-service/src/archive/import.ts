/**
 * Read a `.maic.zip` archive into a stage document ready for the write path.
 *
 * This module answers exactly one question — "what does this file claim to
 * contain, and is that claim well formed?" — and nothing about ownership. The
 * caller decides where the document lands, from its own assertion and path. An
 * archive is a file a student can hand to someone else; nothing inside it may
 * name a user, a course or a workspace, and this module never looks for one.
 *
 * Four rules keep a hostile archive from becoming a plausible one:
 *
 * - the archive size is bounded before it is decoded at all;
 * - a `format_version` newer than this build is refused, not partially read;
 * - the entry set must be *exactly* what a version-1 archive declares — an extra
 *   entry is meaning this build cannot represent, so it cannot be ignored;
 * - the stage document still goes through `prepareStage`, so an imported stage
 *   meets the same migration, sanitizing and validation as an edited one.
 */

import { WorkspaceError } from '../workspace/errors.ts';
import { MANIFEST_PATH, MAX_ARCHIVE_BYTES, parseManifest, type MaicManifest, type MaicManifestResource } from './manifest.ts';
import { readZip } from './zip.ts';

export interface ReadArchiveResult {
  manifest: MaicManifest;
  document: unknown;
  resources: Array<{ manifest: MaicManifestResource; payload: Buffer | null }>;
  archiveBytes: number;
}

/** Strict base64: Node's decoder quietly skips invalid characters, which would
 * let a malformed payload decode into something plausible. */
export function decodeArchivePayload(value: unknown): Buffer {
  if (typeof value !== 'string' || value.length === 0) {
    throw new WorkspaceError('invalid_request', 'archive must be a base64 string');
  }
  // Bounded before decoding: 4/3 of the cap plus padding is the most a legal
  // payload can be, so an oversize body never allocates a buffer.
  const maxEncodedLength = Math.ceil(MAX_ARCHIVE_BYTES / 3) * 4 + 4;
  if (value.length > maxEncodedLength) {
    throw new WorkspaceError('document_rejected', `archive exceeds ${MAX_ARCHIVE_BYTES} bytes`);
  }
  if (value.length % 4 !== 0 || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) {
    throw new WorkspaceError('invalid_request', 'archive is not valid base64');
  }
  const buffer = Buffer.from(value, 'base64');
  if (buffer.length === 0) {
    throw new WorkspaceError('invalid_request', 'archive is empty');
  }
  if (buffer.length > MAX_ARCHIVE_BYTES) {
    throw new WorkspaceError('document_rejected', `archive exceeds ${MAX_ARCHIVE_BYTES} bytes`);
  }
  return buffer;
}

export function readArchive(archive: Buffer): ReadArchiveResult {
  if (archive.length > MAX_ARCHIVE_BYTES) {
    throw new WorkspaceError('document_rejected', `archive exceeds ${MAX_ARCHIVE_BYTES} bytes`);
  }

  const entries = readZip(archive);
  const byName = new Map(entries.map((entry) => [entry.name, entry]));

  const manifestEntry = byName.get(MANIFEST_PATH);
  if (!manifestEntry) {
    throw new WorkspaceError('document_rejected', `archive has no ${MANIFEST_PATH}`);
  }
  let manifestRaw: unknown;
  try {
    manifestRaw = JSON.parse(manifestEntry.data.toString('utf8'));
  } catch {
    throw new WorkspaceError('document_rejected', 'manifest is not valid JSON');
  }
  const manifest = parseManifest(manifestRaw);

  const stageEntry = byName.get(manifest.stage.path);
  if (!stageEntry) {
    throw new WorkspaceError('document_rejected', `archive is missing the stage it declares`);
  }
  const resourcePaths = new Set(manifest.resources.map((resource) => resource.path).filter((path): path is string => Boolean(path)));
  const allowed = new Set([MANIFEST_PATH, manifest.stage.path, ...resourcePaths]);
  if (entries.some((entry) => !allowed.has(entry.name)) || entries.length !== 2 + resourcePaths.size) {
    const unexpected = entries.map((entry) => entry.name).filter((name) => !allowed.has(name));
    throw new WorkspaceError(
      'document_rejected',
      `archive holds entries this format version does not define: ${unexpected.join(', ') || 'resource entries are incomplete'}`,
    );
  }

  const resources = manifest.resources.map((resource) => {
    const entry = resource.path ? byName.get(resource.path) : undefined;
    if (resource.path && !entry) throw new WorkspaceError('document_rejected', `archive is missing resource ${resource.path}`);
    if (entry && entry.data.length !== resource.byte_size) {
      throw new WorkspaceError('document_rejected', `resource ${resource.filename} does not match byte_size`);
    }
    return { manifest: resource, payload: entry?.data ?? null };
  });

  let document: unknown;
  try {
    document = JSON.parse(stageEntry.data.toString('utf8'));
  } catch {
    throw new WorkspaceError('document_rejected', 'stage document is not valid JSON');
  }

  return {
    manifest,
    document,
    resources,
    archiveBytes: archive.length,
  };
}
