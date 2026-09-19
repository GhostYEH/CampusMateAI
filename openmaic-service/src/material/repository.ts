/**
 * Material persistence.
 *
 * The same invariant as the workspace and discovery repositories holds here, and
 * for the same reason: **ownership is part of every predicate**. A material id
 * is resolved with `user_id = ? AND course_id = ?` in the query itself, so a
 * foreign id behaves exactly like an id that never existed and this module never
 * becomes an existence oracle.
 *
 * Two decisions are specific to materials:
 *
 * - **The digest is the identity of a live row.** `uploadMaterial` looks up
 *   `(user_id, course_id, sha256)` among live rows first, so a retry or a
 *   re-selected file returns the existing material instead of cloning it. The
 *   unique index that backs this is partial, so a soft-deleted row does not
 *   block a genuine re-upload.
 * - **The full text travels only on the single fetch that reads it.** A listing
 *   is a navigation surface; shipping every document body on it would make the
 *   list cost grow with the corpus. `text_chars` is what the list needs.
 */

import { randomUUID } from 'node:crypto';

import type { ServiceDatabase } from '../db/database.ts';
import { decodeCursor, encodeCursor } from '../workspace/cursor.ts';
import { WorkspaceError, notFound } from '../workspace/errors.ts';
import { clampLimit, type Page } from '../workspace/repository.ts';

export type ExtractionStatus = 'extracted' | 'unsupported' | 'empty';

export const EXTRACTION_STATUSES: readonly ExtractionStatus[] = ['extracted', 'unsupported', 'empty'];

/** A material body is bounded well below the transport cap; see `MAX_REQUEST_BODY_BYTES`. */
export const MAX_MATERIAL_BYTES = 2 * 1024 * 1024;
export const MAX_MATERIAL_TEXT_BYTES = 512 * 1024;
export const MAX_FILENAME_LENGTH = 255;
export const MAX_MEDIA_TYPE_LENGTH = 200;
export const MAX_REFERENCE_COUNT = 50;

/** A row without its body, as returned by a listing. */
export interface MaterialSummary {
  id: string;
  user_id: string;
  course_id: string;
  filename: string;
  media_type: string;
  byte_size: number;
  sha256: string;
  extraction_status: ExtractionStatus;
  text_chars: number;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface MaterialRecord extends Omit<MaterialSummary, 'text_chars'> {
  text: string;
}

/** A reference a stage may cite: enough to render and to link, never the body. */
export interface MaterialReference {
  id: string;
  filename: string;
  media_type: string;
  extraction_status: ExtractionStatus;
  text_chars: number;
  updated_at: string;
}

export interface ReferenceResolution {
  resolved: MaterialReference[];
  unresolved: string[];
}

export interface CreateMaterialInput {
  userId: string;
  courseId: string;
  filename: string;
  mediaType: string;
  byteSize: number;
  sha256: string;
  extractionStatus: ExtractionStatus;
  text: string;
  payload?: Buffer;
  now?: string;
}

const SUMMARY_COLUMNS = `id, user_id, course_id, filename, media_type, byte_size, sha256,
       extraction_status, length(text_content) AS text_chars, revision, created_at, updated_at`;

const RECORD_COLUMNS = `id, user_id, course_id, filename, media_type, byte_size, sha256,
       extraction_status, text_content AS text, revision, created_at, updated_at`;

export class MaterialRepository {
  readonly #database: ServiceDatabase;

  constructor(database: ServiceDatabase) {
    this.#database = database;
  }

  get #db() {
    return this.#database.raw;
  }

  /**
   * Insert, or return the live row that already carries this digest.
   *
   * The lookup and the insert share the caller's transaction, so two concurrent
   * uploads of the same file cannot both observe "absent" and both insert; the
   * second one hits the partial unique index and is retried as a lookup.
   */
  createMaterial(input: CreateMaterialInput): { material: MaterialSummary; deduplicated: boolean } {
    const existing = this.#findByDigest(input.userId, input.courseId, input.sha256);
    if (existing) return { material: existing, deduplicated: true };

    const now = input.now ?? new Date().toISOString();
    const id = `mt_${randomUUID().replaceAll('-', '')}`;
    try {
      this.#db
        .prepare(
          `INSERT INTO materials (id, user_id, course_id, filename, media_type, byte_size, sha256,
                                 extraction_status, text_content, payload, revision, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)`,
        )
        .run(
          id,
          input.userId,
          input.courseId,
          input.filename,
          input.mediaType,
          input.byteSize,
          input.sha256,
          input.extractionStatus,
          input.text,
          input.payload ?? null,
          now,
          now,
        );
    } catch (error) {
      const raced = this.#findByDigest(input.userId, input.courseId, input.sha256);
      if (raced) return { material: raced, deduplicated: true };
      throw error;
    }
    return {
      material: this.#getSummaryById(input.userId, input.courseId, id),
      deduplicated: false,
    };
  }

  #getSummaryById(userId: string, courseId: string, materialId: string): MaterialSummary {
    const row = this.#db
      .prepare(
        `SELECT ${SUMMARY_COLUMNS}
           FROM materials
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .get(materialId, userId, courseId) as MaterialSummary | undefined;
    if (!row) notFound();
    return row;
  }

  #findByDigest(userId: string, courseId: string, sha256: string): MaterialSummary | null {
    const row = this.#db
      .prepare(
        `SELECT ${SUMMARY_COLUMNS}
           FROM materials
          WHERE user_id = ? AND course_id = ? AND sha256 = ? AND deleted_at IS NULL`,
      )
      .get(userId, courseId, sha256) as MaterialSummary | undefined;
    return row ?? null;
  }

  listMaterials(input: {
    userId: string;
    courseId: string;
    limit?: number;
    cursor?: string | null;
  }): Page<MaterialSummary> {
    const limit = clampLimit(input.limit);
    const cursor = decodeCursor(input.cursor);
    const params: unknown[] = [input.userId, input.courseId];
    let keyset = '';
    if (cursor) {
      keyset = ' AND (updated_at, id) < (?, ?)';
      params.push(cursor.updatedAt, cursor.id);
    }
    params.push(limit + 1);
    const rows = this.#db
      .prepare(
        `SELECT ${SUMMARY_COLUMNS}
           FROM materials
          WHERE user_id = ? AND course_id = ? AND deleted_at IS NULL${keyset}
          ORDER BY updated_at DESC, id DESC
          LIMIT ?`,
      )
      .all(...(params as never[])) as unknown as MaterialSummary[];

    const hasMore = rows.length > limit;
    const items = hasMore ? rows.slice(0, limit) : rows;
    const last = items.at(-1);
    return {
      items,
      nextCursor: hasMore && last ? encodeCursor({ updatedAt: last.updated_at, id: last.id }) : null,
    };
  }

  getMaterial(input: { userId: string; courseId: string; materialId: string }): MaterialRecord {
    const row = this.#db
      .prepare(
        `SELECT ${RECORD_COLUMNS}
           FROM materials
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .get(input.materialId, input.userId, input.courseId) as MaterialRecord | undefined;
    if (!row) notFound();
    return row;
  }

  /** Conditional delete: the caller's expected revision is part of the predicate. */
  softDeleteMaterial(input: {
    userId: string;
    courseId: string;
    materialId: string;
    expectedRevision: number;
    now?: string;
  }): void {
    const now = input.now ?? new Date().toISOString();
    const result = this.#db
      .prepare(
        `UPDATE materials
            SET deleted_at = ?, updated_at = ?, revision = revision + 1
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL AND revision = ?`,
      )
      .run(now, now, input.materialId, input.userId, input.courseId, input.expectedRevision);
    if (Number(result.changes) === 0) {
      // Distinguish "not yours / not there" from "you read a stale revision", but
      // only after confirming the row really is visible to this caller.
      const visible = this.#db
        .prepare(
          `SELECT 1 AS present FROM materials
            WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
        )
        .get(input.materialId, input.userId, input.courseId);
      if (!visible) notFound();
      throw new WorkspaceError('revision_mismatch');
    }
  }

  /**
   * Resolve a batch of ids into authorized references.
   *
   * Order follows the request and duplicates collapse, so a stage that cites the
   * same material twice reads back the citation once. Anything that is not a
   * live material of this caller in this course lands in `unresolved` — the
   * caller is told *that* it did not resolve, never *why*.
   */
  resolveReferences(input: {
    userId: string;
    courseId: string;
    materialIds: readonly string[];
  }): ReferenceResolution {
    const ordered: string[] = [];
    const seen = new Set<string>();
    for (const id of input.materialIds) {
      if (seen.has(id)) continue;
      seen.add(id);
      ordered.push(id);
    }
    if (ordered.length === 0) return { resolved: [], unresolved: [] };

    const placeholders = ordered.map(() => '?').join(', ');
    const rows = this.#db
      .prepare(
        `SELECT id, filename, media_type, extraction_status,
                length(text_content) AS text_chars, updated_at
           FROM materials
          WHERE id IN (${placeholders}) AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .all(...(ordered as never[]), input.userId, input.courseId) as unknown as MaterialReference[];

    const byId = new Map(rows.map((row) => [row.id, row]));
    const resolved: MaterialReference[] = [];
    const unresolved: string[] = [];
    for (const id of ordered) {
      const row = byId.get(id);
      if (row) resolved.push(row);
      else unresolved.push(id);
    }
    return { resolved, unresolved };
  }
}
