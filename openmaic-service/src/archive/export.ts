/**
 * Export one stage as a `.maic.zip` archive.
 *
 * The document is re-serialized through `JSON.parse` → `JSON.stringify(…, null,
 * 2)` rather than embedded as the stored bytes: the archive is meant to be opened
 * and read by a person when something goes wrong, and pretty-printed JSON is
 * what makes that possible. The round-trip is stable for a fixed document, so the
 * same stage always exports to the same bytes.
 */

import { createHash } from 'node:crypto';

import type { StageRow } from '../workspace/repository.ts';
import type { MaterialArchiveRecord } from '../material/repository.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import {
  MANIFEST_PATH,
  MAX_ARCHIVE_BYTES,
  buildManifest,
  archiveFilename,
  stagePathFor,
  type MaicManifestResource,
} from './manifest.ts';
import { writeZip } from './zip.ts';

export interface ExportedArchive {
  archive: Buffer;
  filename: string;
  stageTitle: string;
  dslVersion: string;
  byteSize: number;
  sha256: string;
}

export interface ExportStageInput {
  stage: StageRow;
  workspaceName: string;
  exportedAt: string;
  materials?: MaterialArchiveRecord[];
}

function resourcePathFor(material: MaterialArchiveRecord): string | null {
  return material.payload ? `resources/${material.sha256}.bin` : null;
}

export function exportStage(input: ExportStageInput): ExportedArchive {
  let document: unknown;
  try {
    document = JSON.parse(input.stage.document);
  } catch {
    // A stored document that is not JSON means the row was written outside the
    // DSL write path. Refusing to export it is the only answer that does not
    // produce an archive nobody can import.
    throw new WorkspaceError('document_rejected', 'stored stage document is not valid JSON');
  }

  const stagePath = stagePathFor(input.stage.id);
  const resources: MaicManifestResource[] = (input.materials ?? []).map((material) => ({
    path: resourcePathFor(material),
    source_id: material.id,
    filename: material.filename,
    media_type: material.media_type,
    byte_size: Number(material.byte_size),
    sha256: material.sha256,
    extraction_status: material.extraction_status,
    text: material.text,
  }));
  const manifest = buildManifest({
    exportedAt: input.exportedAt,
    workspaceName: input.workspaceName,
    title: input.stage.title,
    dslVersion: input.stage.dsl_version,
    stagePath,
    resources,
  });

  const archive = writeZip(
    [
      { name: MANIFEST_PATH, data: Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`, 'utf8') },
      { name: stagePath, data: Buffer.from(`${JSON.stringify(document, null, 2)}\n`, 'utf8') },
      ...(input.materials ?? []).flatMap((material) => {
        const path = resourcePathFor(material);
        return path && material.payload ? [{ name: path, data: material.payload }] : [];
      }),
    ],
    { modifiedAt: new Date(input.exportedAt) },
  );

  if (archive.length > MAX_ARCHIVE_BYTES) {
    // Refused rather than truncated: an archive that silently lost the tail of a
    // stage is worse than an export that says why it could not run.
    throw new WorkspaceError(
      'document_rejected',
      `archive would exceed ${MAX_ARCHIVE_BYTES} bytes`,
    );
  }

  return {
    archive,
    filename: archiveFilename(input.stage.title),
    stageTitle: input.stage.title,
    dslVersion: input.stage.dsl_version,
    byteSize: archive.length,
    sha256: createHash('sha256').update(archive).digest('hex'),
  };
}
