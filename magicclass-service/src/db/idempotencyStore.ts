/**
 * Idempotency-key storage shared by every mutating internal route.
 *
 * The record is keyed by `(user_id, key)`, so two callers can use the same key
 * without colliding. A key reused with a *different* body is a client bug rather
 * than a retry: replaying the first response would silently discard the second
 * request, so it is reported as a conflict instead.
 *
 * `requestHash` is computed by the caller and is expected to cover the route as
 * well as the body, otherwise the same key on two paths could replay the wrong
 * answer.
 */

import type { ServiceDatabase } from './database.ts';
import { WorkspaceError } from '../workspace/errors.ts';

interface IdempotencyRecord {
  request_hash: string;
  status: number;
  response_body: string;
}

export interface ReplayedResponse {
  status: number;
  body: Record<string, unknown>;
}

export class IdempotencyStore {
  readonly #database: ServiceDatabase;

  constructor(database: ServiceDatabase) {
    this.#database = database;
  }

  lookup(userId: string, key: string, requestHash: string): ReplayedResponse | null {
    const row = this.#database.raw
      .prepare('SELECT request_hash, status, response_body FROM idempotency_keys WHERE user_id = ? AND key = ?')
      .get(userId, key) as IdempotencyRecord | undefined;
    if (!row) return null;
    if (row.request_hash !== requestHash) {
      throw new WorkspaceError('idempotency_conflict');
    }
    return { status: Number(row.status), body: JSON.parse(row.response_body) as Record<string, unknown> };
  }

  record(
    userId: string,
    key: string,
    scope: { courseId: string; method: string; path: string },
    requestHash: string,
    response: ReplayedResponse,
  ): void {
    this.#database.raw
      .prepare(
        `INSERT INTO idempotency_keys (key, user_id, course_id, method, path, request_hash, status, response_body, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(user_id, key) DO NOTHING`,
      )
      .run(
        key,
        userId,
        scope.courseId,
        scope.method,
        scope.path,
        requestHash,
        response.status,
        JSON.stringify(response.body),
        Date.now(),
      );
  }
}
