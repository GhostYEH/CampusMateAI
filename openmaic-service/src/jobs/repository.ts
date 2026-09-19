import { createHash, randomUUID } from 'node:crypto';

import type { ServiceDatabase } from '../db/database.ts';
import { WorkspaceError, notFound } from '../workspace/errors.ts';

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobRow {
  id: string;
  user_id: string;
  course_id: string;
  kind: string;
  mode: string;
  input_json: string;
  status: JobStatus;
  progress: number;
  attempts: number;
  error_code: string | null;
  artifact_id: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancelled_at: string | null;
}

export interface ArtifactRow {
  id: string;
  job_id: string;
  user_id: string;
  course_id: string;
  filename: string;
  media_type: string;
  byte_size: number;
  sha256: string;
  payload: Buffer;
  created_at: string;
}

export function jobRequestHash(input: unknown): string {
  return createHash('sha256').update(JSON.stringify(input ?? null), 'utf8').digest('hex');
}

function nowIso() {
  return new Date().toISOString();
}

export class JobRepository {
  readonly #database: ServiceDatabase;

  constructor(database: ServiceDatabase) {
    this.#database = database;
  }

  get #db() {
    return this.#database.raw;
  }

  create(input: {
    userId: string;
    courseId: string;
    kind: string;
    mode: string;
    request: unknown;
    now?: string;
  }): JobRow {
    const now = input.now ?? nowIso();
    const id = `job_${randomUUID().replaceAll('-', '')}`;
    this.#db.prepare(
      `INSERT INTO jobs (id, user_id, course_id, kind, mode, input_json, status, progress, attempts, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, 'queued', 0, 0, ?, ?)`,
    ).run(id, input.userId, input.courseId, input.kind, input.mode, JSON.stringify(input.request), now, now);
    return this.get({ userId: input.userId, courseId: input.courseId, jobId: id });
  }

  get(input: { userId: string; courseId: string; jobId: string }): JobRow {
    const row = this.#db.prepare(
      `SELECT id, user_id, course_id, kind, mode, input_json, status, progress, attempts,
              error_code, artifact_id, created_at, updated_at, started_at, finished_at, cancelled_at
         FROM jobs
        WHERE id = ? AND user_id = ? AND course_id = ?`,
    ).get(input.jobId, input.userId, input.courseId) as JobRow | undefined;
    if (!row) notFound();
    return row;
  }

  cancel(input: { userId: string; courseId: string; jobId: string; now?: string }): JobRow {
    const current = this.get(input);
    if (current.status === 'completed') throw new WorkspaceError('invalid_request', 'completed jobs cannot be cancelled');
    if (current.status === 'cancelled') return current;
    const now = input.now ?? nowIso();
    this.#db.prepare(
      `UPDATE jobs SET status = 'cancelled', cancelled_at = ?, updated_at = ?
        WHERE id = ? AND user_id = ? AND course_id = ? AND status IN ('queued', 'running', 'failed')`,
    ).run(now, now, input.jobId, input.userId, input.courseId);
    return this.get(input);
  }

  retry(input: { userId: string; courseId: string; jobId: string; now?: string }): JobRow {
    const current = this.get(input);
    if (!['failed', 'cancelled'].includes(current.status)) {
      throw new WorkspaceError('invalid_request', 'only failed or cancelled jobs can be retried');
    }
    const now = input.now ?? nowIso();
    this.#db.prepare(
      `UPDATE jobs SET status = 'queued', progress = 0, error_code = NULL, cancelled_at = NULL,
              finished_at = NULL, started_at = NULL, attempts = attempts + 1, updated_at = ?
        WHERE id = ? AND user_id = ? AND course_id = ?`,
    ).run(now, input.jobId, input.userId, input.courseId);
    return this.get(input);
  }

  markRunning(input: { jobId: string; userId: string; courseId: string; now?: string }): JobRow {
    const now = input.now ?? nowIso();
    this.#db.prepare(
      `UPDATE jobs SET status = 'running', progress = 1, attempts = attempts + 1, started_at = ?, updated_at = ?
        WHERE id = ? AND user_id = ? AND course_id = ? AND status = 'queued'`,
    ).run(now, now, input.jobId, input.userId, input.courseId);
    return this.get(input);
  }

  complete(input: {
    userId: string;
    courseId: string;
    jobId: string;
    artifact: { filename: string; mediaType: string; payload: Buffer };
    now?: string;
  }): JobRow {
    const current = this.get(input);
    if (current.status === 'cancelled') throw new WorkspaceError('invalid_request', 'cancelled jobs cannot complete');
    const now = input.now ?? nowIso();
    const artifactId = `artifact_${randomUUID().replaceAll('-', '')}`;
    const digest = createHash('sha256').update(input.artifact.payload).digest('hex');
    this.#db.prepare(
      `INSERT INTO artifacts (id, job_id, user_id, course_id, filename, media_type, byte_size, sha256, payload, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(artifactId, input.jobId, input.userId, input.courseId, input.artifact.filename,
      input.artifact.mediaType, input.artifact.payload.byteLength, digest, input.artifact.payload, now);
    this.#db.prepare(
      `UPDATE jobs SET status = 'completed', progress = 100, artifact_id = ?, finished_at = ?, updated_at = ?, error_code = NULL
        WHERE id = ? AND user_id = ? AND course_id = ?`,
    ).run(artifactId, now, now, input.jobId, input.userId, input.courseId);
    return this.get(input);
  }

  fail(input: { userId: string; courseId: string; jobId: string; errorCode: string; now?: string }): JobRow {
    const current = this.get(input);
    if (current.status === 'cancelled') return current;
    const now = input.now ?? nowIso();
    this.#db.prepare(
      `UPDATE jobs SET status = 'failed', error_code = ?, finished_at = ?, updated_at = ?
        WHERE id = ? AND user_id = ? AND course_id = ?`,
    ).run(input.errorCode.slice(0, 80), now, now, input.jobId, input.userId, input.courseId);
    return this.get(input);
  }

  getArtifact(input: { userId: string; courseId: string; artifactId: string }): ArtifactRow {
    const row = this.#db.prepare(
      `SELECT id, job_id, user_id, course_id, filename, media_type, byte_size, sha256, payload, created_at
         FROM artifacts WHERE id = ? AND user_id = ? AND course_id = ?`,
    ).get(input.artifactId, input.userId, input.courseId) as ArtifactRow | undefined;
    if (!row) notFound();
    return row;
  }
}
