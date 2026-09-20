/**
 * Workspace + Stage persistence.
 *
 * Two invariants hold for every statement in this file:
 *
 * 1. **Ownership is part of the query, never a follow-up check.** Every read and
 *    write carries `user_id = ? AND course_id = ?`, so a row that belongs to
 *    another user or another course cannot be observed even transiently. A
 *    post-hoc `if (row.user_id !== userId) throw` is one refactor away from
 *    being dropped; a missing WHERE clause fails loudly instead.
 * 2. **Concurrency is decided by the database.** Updates carry the caller's
 *    expected revision in the WHERE clause and inspect `changes`; there is no
 *    read-then-write window. The route handler runs inside the request
 *    transaction, so the revision check and the row update commit together.
 *
 * Soft delete is used throughout: a deleted row keeps its id, so a client
 * holding a stale id gets a clean 404 instead of a different row reusing it.
 */

import { createHash, randomUUID } from 'node:crypto';

import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import { folderIsOwned } from '../discovery/ownership.ts';
import { upgradeLegacySlideCanvases } from '../dsl/slide-canvas.ts';
import { decodeCursor, encodeCursor } from './cursor.ts';
import { WorkspaceError, notFound } from './errors.ts';

export interface WorkspaceRow {
  id: string;
  user_id: string;
  course_id: string;
  name: string;
  description: string;
  folder_id: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface StageRow {
  id: string;
  workspace_id: string;
  user_id: string;
  course_id: string;
  title: string;
  document: string;
  dsl_version: string;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  nextCursor: string | null;
}

export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 50;

export function clampLimit(limit: number | undefined): number {
  if (limit === undefined || !Number.isFinite(limit)) return DEFAULT_PAGE_SIZE;
  const integer = Math.floor(limit);
  if (integer < 1) return DEFAULT_PAGE_SIZE;
  return Math.min(integer, MAX_PAGE_SIZE);
}

/** Deterministic digest of a request body, used to detect idempotency-key reuse. */
export function hashRequest(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value ?? null), 'utf8').digest('hex');
}

export interface ReplayedResponse {
  status: number;
  body: Record<string, unknown>;
}

export class WorkspaceRepository {
  readonly #database: ServiceDatabase;
  /**
   * Idempotency now lives in one place so a second route module cannot grow its
   * own subtly different replay rule. These two methods stay as the class's
   * public surface for the existing callers.
   */
  readonly #idempotency: IdempotencyStore;

  constructor(database: ServiceDatabase) {
    this.#database = database;
    this.#idempotency = new IdempotencyStore(database);
  }

  get #db() {
    return this.#database.raw;
  }

  // ===== idempotency =====

  lookupIdempotency(userId: string, key: string, requestHash: string): ReplayedResponse | null {
    return this.#idempotency.lookup(userId, key, requestHash);
  }

  recordIdempotency(
    userId: string,
    key: string,
    scope: { courseId: string; method: string; path: string },
    requestHash: string,
    response: ReplayedResponse,
  ): void {
    this.#idempotency.record(userId, key, scope, requestHash, response);
  }

  // ===== workspaces =====

  createWorkspace(input: {
    userId: string;
    courseId: string;
    name: string;
    description?: string;
    folderId?: string | null;
    now?: string;
  }): WorkspaceRow {
    const now = input.now ?? new Date().toISOString();
    const folderId = input.folderId ?? null;
    // Filing is only ever into the caller's own folder in this course; a foreign
    // id is answered exactly like a missing one.
    if (folderId !== null && !folderIsOwned(this.#database, { ...input, folderId })) notFound();
    const id = `ws_${randomUUID().replaceAll('-', '')}`;
    this.#db
      .prepare(
        `INSERT INTO workspaces (id, user_id, course_id, name, description, folder_id, revision, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)`,
      )
      .run(id, input.userId, input.courseId, input.name, input.description ?? '', folderId, now, now);
    return this.getWorkspace({ userId: input.userId, courseId: input.courseId, workspaceId: id });
  }

  listWorkspaces(input: {
    userId: string;
    courseId: string;
    limit?: number;
    cursor?: string | null;
  }): Page<WorkspaceRow> {
    const limit = clampLimit(input.limit);
    const cursor = decodeCursor(input.cursor);
    const params: unknown[] = [input.userId, input.courseId];
    let keyset = '';
    if (cursor) {
      // Row-value comparison keeps the ORDER BY and the filter on the same key.
      keyset = ' AND (updated_at, id) < (?, ?)';
      params.push(cursor.updatedAt, cursor.id);
    }
    params.push(limit + 1);
    const rows = this.#db
      .prepare(
        `SELECT id, user_id, course_id, name, description, folder_id, revision, created_at, updated_at
           FROM workspaces
          WHERE user_id = ? AND course_id = ? AND deleted_at IS NULL${keyset}
          ORDER BY updated_at DESC, id DESC
          LIMIT ?`,
      )
      .all(...(params as never[])) as unknown as WorkspaceRow[];

    const hasMore = rows.length > limit;
    const items = hasMore ? rows.slice(0, limit) : rows;
    const last = items.at(-1);
    return {
      items,
      nextCursor: hasMore && last ? encodeCursor({ updatedAt: last.updated_at, id: last.id }) : null,
    };
  }

  getWorkspace(input: { userId: string; courseId: string; workspaceId: string }): WorkspaceRow {
    const row = this.#db
      .prepare(
        `SELECT id, user_id, course_id, name, description, folder_id, revision, created_at, updated_at
           FROM workspaces
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .get(input.workspaceId, input.userId, input.courseId) as WorkspaceRow | undefined;
    if (!row) notFound();
    return row;
  }

  updateWorkspace(input: {
    userId: string;
    courseId: string;
    workspaceId: string;
    expectedRevision: number;
    /** `null` moves the workspace back to the unfiled list. */
    patch: { name?: string; description?: string; folderId?: string | null };
    now?: string;
  }): WorkspaceRow {
    const now = input.now ?? new Date().toISOString();
    const assignments: string[] = [];
    const params: unknown[] = [];
    if (input.patch.name !== undefined) {
      assignments.push('name = ?');
      params.push(input.patch.name);
    }
    if (input.patch.description !== undefined) {
      assignments.push('description = ?');
      params.push(input.patch.description);
    }
    if (input.patch.folderId !== undefined) {
      const folderId = input.patch.folderId;
      if (folderId !== null && !folderIsOwned(this.#database, { ...input, folderId })) notFound();
      assignments.push('folder_id = ?');
      params.push(folderId);
    }
    if (assignments.length === 0) {
      throw new WorkspaceError('invalid_request', 'no updatable field was provided');
    }
    assignments.push('revision = revision + 1', 'updated_at = ?');
    params.push(now, input.workspaceId, input.userId, input.courseId, input.expectedRevision);
    const result = this.#db
      .prepare(
        `UPDATE workspaces SET ${assignments.join(', ')}
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL AND revision = ?`,
      )
      .run(...(params as never[]));
    if (Number(result.changes) === 0) this.#revisionFailure(input.userId, input.courseId, input.workspaceId, 'workspaces');
    return this.getWorkspace(input);
  }

  softDeleteWorkspace(input: {
    userId: string;
    courseId: string;
    workspaceId: string;
    expectedRevision: number;
    now?: string;
  }): void {
    const now = input.now ?? new Date().toISOString();
    const result = this.#db
      .prepare(
        `UPDATE workspaces SET deleted_at = ?, updated_at = ?, revision = revision + 1
          WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL AND revision = ?`,
      )
      .run(now, now, input.workspaceId, input.userId, input.courseId, input.expectedRevision);
    if (Number(result.changes) === 0) this.#revisionFailure(input.userId, input.courseId, input.workspaceId, 'workspaces');
    // Soft-deleting a workspace must not leave its stages reachable by id.
    this.#db
      .prepare(
        `UPDATE stages SET deleted_at = ?, updated_at = ?
          WHERE workspace_id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .run(now, now, input.workspaceId, input.userId, input.courseId);
  }

  /**
   * Distinguish "the row is gone" from "the row moved on".
   *
   * A failed conditional UPDATE is ambiguous on its own; reporting it as a
   * revision conflict for a row that no longer exists would send the client into
   * a retry loop it can never win.
   */
  #revisionFailure(userId: string, courseId: string, id: string, table: string): never {
    const existing = this.#db
      .prepare(`SELECT revision FROM ${table} WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`)
      .get(id, userId, courseId) as { revision: number } | undefined;
    if (!existing) notFound();
    throw new WorkspaceError('revision_mismatch');
  }

  // ===== stages =====

  createStage(input: {
    userId: string;
    courseId: string;
    workspaceId: string;
    title: string;
    document: unknown;
    dslVersion: string;
    now?: string;
  }): StageRow {
    // The workspace must exist and belong to this caller before its child does.
    this.getWorkspace(input);
    const now = input.now ?? new Date().toISOString();
    const id = `stg_${randomUUID().replaceAll('-', '')}`;
    this.#db
      .prepare(
        `INSERT INTO stages (id, workspace_id, user_id, course_id, title, document, dsl_version, revision, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)`,
      )
      .run(
        id,
        input.workspaceId,
        input.userId,
        input.courseId,
        input.title,
        JSON.stringify(input.document),
        input.dslVersion,
        now,
        now,
      );
    return this.getStage({
      userId: input.userId,
      courseId: input.courseId,
      workspaceId: input.workspaceId,
      stageId: id,
    });
  }

  listStages(input: {
    userId: string;
    courseId: string;
    workspaceId: string;
    limit?: number;
    cursor?: string | null;
  }): Page<StageRow> {
    this.getWorkspace(input);
    const limit = clampLimit(input.limit);
    const cursor = decodeCursor(input.cursor);
    const params: unknown[] = [input.userId, input.courseId, input.workspaceId];
    let keyset = '';
    if (cursor) {
      keyset = ' AND (updated_at, id) < (?, ?)';
      params.push(cursor.updatedAt, cursor.id);
    }
    params.push(limit + 1);
    const rows = this.#db
      .prepare(
        `SELECT id, workspace_id, user_id, course_id, title, document, dsl_version, revision, created_at, updated_at
           FROM stages
          WHERE user_id = ? AND course_id = ? AND workspace_id = ? AND deleted_at IS NULL${keyset}
          ORDER BY updated_at DESC, id DESC
          LIMIT ?`,
      )
      .all(...(params as never[])) as unknown as StageRow[];

    const hasMore = rows.length > limit;
    const items = hasMore ? rows.slice(0, limit) : rows;
    const last = items.at(-1);
    return {
      items,
      nextCursor: hasMore && last ? encodeCursor({ updatedAt: last.updated_at, id: last.id }) : null,
    };
  }

  getStage(input: { userId: string; courseId: string; workspaceId: string; stageId: string }): StageRow {
    const row = this.#db
      .prepare(
        `SELECT id, workspace_id, user_id, course_id, title, document, dsl_version, revision, created_at, updated_at
           FROM stages
          WHERE id = ? AND workspace_id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
      )
      .get(input.stageId, input.workspaceId, input.userId, input.courseId) as StageRow | undefined;
    if (!row) notFound();
    // 所有调用方（编辑、播放、导出、归档、渲染）都从这里取文档，所以"历史文档补成
    // 当前形态"只需要挂在这一处。见 `dsl/slide-canvas.ts` 里读时投影的取舍说明。
    return { ...row, document: projectStoredDocument(row.document) };
  }

  replaceStage(input: {
    userId: string;
    courseId: string;
    workspaceId: string;
    stageId: string;
    expectedRevision: number;
    title?: string;
    document: unknown;
    dslVersion: string;
    now?: string;
  }): StageRow {
    const now = input.now ?? new Date().toISOString();
    const params: unknown[] = [JSON.stringify(input.document), input.dslVersion, now];
    let titleClause = '';
    if (input.title !== undefined) {
      titleClause = ', title = ?';
      params.push(input.title);
    }
    params.push(input.stageId, input.workspaceId, input.userId, input.courseId, input.expectedRevision);
    const result = this.#db
      .prepare(
        `UPDATE stages
            SET document = ?, dsl_version = ?, updated_at = ?, revision = revision + 1${titleClause}
          WHERE id = ? AND workspace_id = ? AND user_id = ? AND course_id = ?
            AND deleted_at IS NULL AND revision = ?`,
      )
      .run(...(params as never[]));
    if (Number(result.changes) === 0) this.#revisionFailure(input.userId, input.courseId, input.stageId, 'stages');
    return this.getStage(input);
  }

  softDeleteStage(input: {
    userId: string;
    courseId: string;
    workspaceId: string;
    stageId: string;
    expectedRevision: number;
    now?: string;
  }): void {
    const now = input.now ?? new Date().toISOString();
    const result = this.#db
      .prepare(
        `UPDATE stages SET deleted_at = ?, updated_at = ?, revision = revision + 1
          WHERE id = ? AND workspace_id = ? AND user_id = ? AND course_id = ?
            AND deleted_at IS NULL AND revision = ?`,
      )
      .run(now, now, input.stageId, input.workspaceId, input.userId, input.courseId, input.expectedRevision);
    if (Number(result.changes) === 0) this.#revisionFailure(input.userId, input.courseId, input.stageId, 'stages');
  }
}

/**
 * 把存储的文档投影成当前形态（目前只有一件事：历史幻灯片画布补成真实画布）。
 *
 * 三个刻意的选择：
 *
 * - **解析失败时原样返回存储字节。** 这里不是校验点；把坏 JSON 变成抛错会掩盖真正
 *   该报错的那一层（`prepareStage`），也会让一个只读请求突然 500。
 * - **没有改动时不重新序列化。** 纯投影不该改变字节，重新序列化会白白改变键顺序
 *   与浮点写法，让"没变"变成"看起来变了"。
 * - **不写回数据库。** 投影只影响返回给调用方的视图；存量数据由用户下一次正常编辑
 *   时的写入路径落库。见 `dsl/slide-canvas.ts` 的取舍说明。
 */
function projectStoredDocument(raw: string): string {
  try {
    const parsed: unknown = JSON.parse(raw);
    const projected = upgradeLegacySlideCanvases(parsed);
    return projected === parsed ? raw : JSON.stringify(projected);
  } catch {
    return raw;
  }
}
