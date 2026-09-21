/**
 * Folder tree + keyword search persistence.
 *
 * The same two invariants as the workspace repository hold here, for the same
 * reason:
 *
 * 1. **Ownership is part of every predicate.** A folder id, a parent id and a
 *    search hit are all resolved with `user_id = ? AND course_id = ?` in the
 *    query. A foreign id therefore behaves exactly like an id that never
 *    existed, which is what stops this module from becoming an existence oracle.
 * 2. **Concurrency is decided by the database.** A rename or a delete carries
 *    the caller's expected revision in the `WHERE` clause and inspects
 *    `changes`; there is no read-then-write window.
 *
 * Search is deliberately narrow: it matches titles/names of rows the caller can
 * still open, it treats `%` and `_` as literal characters, and it walks the same
 * keyset cursor as the rest of the service so a page boundary is stable.
 */

import { randomUUID } from 'node:crypto';

import type { ServiceDatabase } from '../db/database.ts';
import { decodeCursor, encodeCursor } from '../workspace/cursor.ts';
import { WorkspaceError, notFound } from '../workspace/errors.ts';
import { MAX_PAGE_SIZE, clampLimit, type Page } from '../workspace/repository.ts';
import { folderIsOwned } from './ownership.ts';

export interface FolderRow {
  id: string;
  user_id: string;
  course_id: string;
  parent_id: string | null;
  name: string;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface FolderListItem extends FolderRow {
  workspace_count: number;
}

export interface SearchHit {
  kind: 'workspace' | 'stage';
  row_id: string;
  workspace_id: string;
  stage_id: string | null;
  title: string;
  snippet: string;
  folder_id: string | null;
  updated_at: string;
}

export const MAX_QUERY_LENGTH = 200;

/**
 * Convert a user keyword into a `LIKE` pattern.
 *
 * `LIKE` treats `%` and `_` as wildcards, so searching for "100%" would
 * otherwise match every row. Escaping the three metacharacters (the escape
 * character itself first) keeps the query literal.
 */
export function likePattern(query: string): string {
  return `%${query.replace(/[\\%_]/g, (character) => `\\${character}`)}%`;
}

/** Build the in-product deep link a search hit must open. */
export function stageDeepLink(courseId: string, workspaceId: string, stageId: string | null): string {
  const parameters = new URLSearchParams({ tab: 'mentoring', workspace: workspaceId });
  if (stageId) parameters.set('stage', stageId);
  return `/courses/${encodeURIComponent(courseId)}?${parameters.toString()}`;
}

/**
 * True only when `folderId` names a live folder owned by this caller in this
 * course. Re-exported for callers that already depend on this module.
 */
export { folderIsOwned };

export class DiscoveryRepository {
  readonly #database: ServiceDatabase;

  constructor(database: ServiceDatabase) {
    this.#database = database;
  }

  get #db() {
    return this.#database.raw;
  }

  // ===== folders =====

  createFolder(input: {
    userId: string;
    courseId: string;
    name: string;
    parentId?: string | null;
    now?: string;
  }): FolderRow {
    const now = input.now ?? new Date().toISOString();
    const parentId = input.parentId ?? null;
    if (parentId !== null && !folderIsOwned(this.#database, { ...input, folderId: parentId })) {
      notFound();
    }
    const id = `fd_${randomUUID().replaceAll('-', '')}`;
    this.#db
      .prepare(
        `INSERT INTO folders (id, user_id, course_id, parent_id, name, revision, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, 1, ?, ?)`,
      )
      .run(id, input.userId, input.courseId, parentId, input.name, now, now);
    return this.getFolder({ userId: input.userId, courseId: input.courseId, folderId: id });
  }

  listFolders(input: {
    userId: string;
    courseId: string;
    limit?: number;
    cursor?: string | null;
  }): Page<FolderListItem> {
    const limit = clampLimit(input.limit);
    const cursor = decodeCursor(input.cursor);
    const params: unknown[] = [input.userId, input.courseId];
    let keyset = '';
    if (cursor) {
      keyset = ' AND (f.updated_at, f.id) < (?, ?)';
      params.push(cursor.updatedAt, cursor.id);
    }
    params.push(limit + 1);
    const rows = this.#db
      .prepare(
        `SELECT f.id, f.user_id, f.course_id, f.parent_id, f.name, f.revision, f.created_at, f.updated_at,
                (SELECT COUNT(*) FROM workspaces w
                  WHERE w.folder_id = f.id AND w.user_id = f.user_id
                    AND w.course_id = f.course_id AND w.deleted_at IS NULL) AS workspace_count
           FROM folders f
          WHERE f.user_id = ? AND f.course_id = ? AND f.deleted_at IS NULL${keyset}
          ORDER BY f.updated_at DESC, f.id DESC
          LIMIT ?`,
      )
      .all(...(params as never[])) as unknown as FolderListItem[];

    const hasMore = rows.length > limit;
    const items = hasMore ? rows.slice(0, limit) : rows;
    const last = items.at(-1);
    return {
      items,
      nextCursor: hasMore && last ? encodeCursor({ updatedAt: last.updated_at, id: last.id }) : null,
    };
  }

  getFolder(input: { userId: string; courseId: string; folderId: string }): FolderRow {
    const row = this.#db
      .prepare(
        `SELECT id, user_id, course_id, parent_id, name, revision, created_at, updated_at
           FROM folders
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .get(input.folderId, input.userId, input.courseId) as FolderRow | undefined;
    if (!row) notFound();
    return row;
  }

  updateFolder(input: {
    userId: string;
    courseId: string;
    folderId: string;
    expectedRevision: number;
    patch: { name?: string; parentId?: string | null };
    now?: string;
  }): FolderRow {
    const now = input.now ?? new Date().toISOString();
    const assignments: string[] = [];
    const params: unknown[] = [];
    if (input.patch.name !== undefined) {
      assignments.push('name = ?');
      params.push(input.patch.name);
    }
    if (input.patch.parentId !== undefined) {
      const parentId = input.patch.parentId;
      if (parentId === null) {
        assignments.push('parent_id = NULL');
      } else {
        // A folder may not become its own ancestor: the check walks up from the
        // proposed parent, so it catches both "parent is me" and "parent is my
        // descendant" without needing a separate descendant query.
        this.#assertNoCycle({ ...input, candidateParentId: parentId });
        assignments.push('parent_id = ?');
        params.push(parentId);
      }
    }
    if (assignments.length === 0) {
      throw new WorkspaceError('invalid_request', 'no updatable field was provided');
    }
    assignments.push('revision = revision + 1', 'updated_at = ?');
    params.push(now, input.folderId, input.userId, input.courseId, input.expectedRevision);
    const result = this.#db
      .prepare(
        `UPDATE folders SET ${assignments.join(', ')}
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL AND revision = ?`,
      )
      .run(...(params as never[]));
    if (Number(result.changes) === 0) this.#revisionFailure(input);
    return this.getFolder(input);
  }

  /**
   * Soft-delete a folder **and its subtree**, and unfile every workspace that
   * lived in it.
   *
   * Refusing to delete a non-empty folder would be defensible, but silently
   * stranding a student's work inside a hidden folder is not: the workspaces are
   * detached rather than deleted, so they stay reachable from the unfiled list.
   */
  softDeleteFolder(input: {
    userId: string;
    courseId: string;
    folderId: string;
    expectedRevision: number;
    now?: string;
  }): void {
    const now = input.now ?? new Date().toISOString();
    const result = this.#db
      .prepare(
        `UPDATE folders SET deleted_at = ?, updated_at = ?, revision = revision + 1
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL AND revision = ?`,
      )
      .run(now, now, input.folderId, input.userId, input.courseId, input.expectedRevision);
    if (Number(result.changes) === 0) this.#revisionFailure(input);

    const subtree = `WITH RECURSIVE subtree(id) AS (
        SELECT id FROM folders
         WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NOT NULL
        UNION ALL
        SELECT child.id FROM folders child
          JOIN subtree ON child.parent_id = subtree.id
         WHERE child.user_id = ? AND child.course_id = ? AND child.deleted_at IS NULL
      )`;

    this.#db
      .prepare(
        `${subtree}
         UPDATE workspaces SET folder_id = NULL, updated_at = ?
          WHERE user_id = ? AND course_id = ? AND deleted_at IS NULL
            AND folder_id IN (SELECT id FROM subtree)`,
      )
      .run(
        input.folderId,
        input.userId,
        input.courseId,
        input.userId,
        input.courseId,
        now,
        input.userId,
        input.courseId,
      );

    this.#db
      .prepare(
        `${subtree}
         UPDATE folders SET deleted_at = ?, updated_at = ?, revision = revision + 1
          WHERE user_id = ? AND course_id = ? AND deleted_at IS NULL
            AND id IN (SELECT id FROM subtree)`,
      )
      .run(
        input.folderId,
        input.userId,
        input.courseId,
        input.userId,
        input.courseId,
        now,
        now,
        input.userId,
        input.courseId,
      );
  }

  /**
   * Walk up from the proposed parent. The `seen` set bounds the walk even if a
   * previous bug left a cycle in the table, so this can never hang a request.
   */
  #assertNoCycle(input: { userId: string; courseId: string; folderId: string; candidateParentId: string }): void {
    const lookup = this.#db.prepare(
      `SELECT parent_id FROM folders
        WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
    );
    const seen = new Set<string>();
    let current: string | null = input.candidateParentId;
    while (current) {
      if (current === input.folderId) {
        throw new WorkspaceError('invalid_request', 'a folder cannot be moved inside itself');
      }
      if (seen.has(current)) return;
      seen.add(current);
      const row: { parent_id: string | null } | undefined = lookup.get(
        current,
        input.userId,
        input.courseId,
      ) as { parent_id: string | null } | undefined;
      // A missing ancestor is a bad reference, not a cycle; the foreign-key
      // predicate on the parent itself is checked before the update runs.
      if (!row) {
        if (seen.size === 1) notFound();
        return;
      }
      current = row.parent_id;
    }
  }

  #revisionFailure(input: { userId: string; courseId: string; folderId: string }): never {
    const existing = this.#db
      .prepare(
        `SELECT revision FROM folders
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .get(input.folderId, input.userId, input.courseId);
    if (!existing) notFound();
    throw new WorkspaceError('revision_mismatch');
  }

  // ===== search =====

  /**
   * Keyword search over the caller's own workspaces and stages in one course.
   *
   * A stage is only reachable while its workspace is alive, so the stage branch
   * joins the workspace and repeats the ownership predicate there: a hit that
   * cannot be opened is worse than no hit at all.
   */
  search(input: {
    userId: string;
    courseId: string;
    query: string;
    limit?: number;
    cursor?: string | null;
  }): Page<SearchHit> {
    const limit = Math.min(clampLimit(input.limit), MAX_PAGE_SIZE);
    const cursor = decodeCursor(input.cursor);
    const pattern = likePattern(input.query);

    const branches = `
      SELECT 'workspace' AS kind, w.id AS row_id, w.id AS workspace_id, NULL AS stage_id,
             w.name AS title, w.description AS snippet, w.folder_id AS folder_id, w.updated_at AS updated_at
        FROM workspaces w
       WHERE w.user_id = ? AND w.course_id = ? AND w.deleted_at IS NULL
         AND (w.name LIKE ? ESCAPE '\\' OR w.description LIKE ? ESCAPE '\\')
      UNION ALL
      SELECT 'stage' AS kind, s.id AS row_id, s.workspace_id AS workspace_id, s.id AS stage_id,
             s.title AS title, '' AS snippet, w.folder_id AS folder_id, s.updated_at AS updated_at
        FROM stages s
        JOIN workspaces w ON w.id = s.workspace_id
       WHERE s.user_id = ? AND s.course_id = ? AND s.deleted_at IS NULL
         AND w.deleted_at IS NULL AND w.user_id = ? AND w.course_id = ?
         AND s.title LIKE ? ESCAPE '\\'`;

    const params: unknown[] = [
      input.userId,
      input.courseId,
      pattern,
      pattern,
      input.userId,
      input.courseId,
      input.userId,
      input.courseId,
      pattern,
    ];
    let keyset = '';
    if (cursor) {
      keyset = ' AND (updated_at, row_id) < (?, ?)';
      params.push(cursor.updatedAt, cursor.id);
    }
    params.push(limit + 1);

    const rows = this.#db
      .prepare(
        `SELECT kind, row_id, workspace_id, stage_id, title, snippet, folder_id, updated_at
           FROM (${branches})
          WHERE 1 = 1${keyset}
          ORDER BY updated_at DESC, row_id DESC
          LIMIT ?`,
      )
      .all(...(params as never[])) as unknown as SearchHit[];

    const hasMore = rows.length > limit;
    const items = hasMore ? rows.slice(0, limit) : rows;
    const last = items.at(-1);
    return {
      items,
      nextCursor: hasMore && last ? encodeCursor({ updatedAt: last.updated_at, id: last.row_id }) : null,
    };
  }
}

export { MAX_PAGE_SIZE };
