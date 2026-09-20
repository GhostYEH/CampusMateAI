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
  /** 讲解任务绑定的场景；非讲解任务为 null。 */
  scene_id: string | null;
  /** 生成该音频所用的讲稿指纹；非讲解任务为 null。 */
  narration_hash: string | null;
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
    sceneId?: string | null;
    narrationHash?: string | null;
    now?: string;
  }): JobRow {
    const now = input.now ?? nowIso();
    const id = `job_${randomUUID().replaceAll('-', '')}`;
    this.#db.prepare(
      `INSERT INTO jobs (id, user_id, course_id, kind, mode, input_json, status, progress, attempts, scene_id, narration_hash, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, 'queued', 0, 0, ?, ?, ?, ?)`,
    ).run(id, input.userId, input.courseId, input.kind, input.mode, JSON.stringify(input.request),
      input.sceneId ?? null, input.narrationHash ?? null, now, now);
    return this.get({ userId: input.userId, courseId: input.courseId, jobId: id });
  }

  get(input: { userId: string; courseId: string; jobId: string }): JobRow {
    const row = this.#db.prepare(
      `SELECT id, user_id, course_id, kind, mode, input_json, status, progress, attempts,
              error_code, artifact_id, scene_id, narration_hash, created_at, updated_at,
              started_at, finished_at, cancelled_at
         FROM jobs
        WHERE id = ? AND user_id = ? AND course_id = ?`,
    ).get(input.jobId, input.userId, input.courseId) as JobRow | undefined;
    if (!row) notFound();
    return row;
  }

  /**
   * 找出某个场景**已完成**的讲解任务。
   *
   * 这是"切换场景 / 刷新页面后仍然挂对页"的读路径：客户端只给 sceneId，
   * 服务端按 (用户, 课程, 场景) 反查，而不是让客户端记住 job 或 artifact id。
   * 只返回 completed：queued/running 的任务由调用方按 job 状态轮询，失败的任务
   * 不应被当成"这一页有音频"。
   */
  findCompletedSceneNarration(input: {
    userId: string;
    courseId: string;
    sceneId: string;
    narrationHash?: string | null;
  }): JobRow | null {
    const hashFilter = input.narrationHash ? 'AND narration_hash = ?' : '';
    const params: unknown[] = [input.userId, input.courseId, input.sceneId];
    if (input.narrationHash) params.push(input.narrationHash);
    const row = this.#db.prepare(
      `SELECT id, user_id, course_id, kind, mode, input_json, status, progress, attempts,
              error_code, artifact_id, scene_id, narration_hash, created_at, updated_at,
              started_at, finished_at, cancelled_at
         FROM jobs
        WHERE user_id = ? AND course_id = ? AND scene_id = ? AND kind = 'tts'
          AND status = 'completed' AND artifact_id IS NOT NULL ${hashFilter}
        ORDER BY updated_at DESC, id DESC LIMIT 1`,
    ).get(...params) as JobRow | undefined;
    return row ?? null;
  }

  /**
   * 找出该场景**正在进行中**的讲解任务。
   *
   * 用于让重复点击复用同一个任务而不是再排一个：学生连点两次"生成讲解"只应
   * 产生一次 MiMo 调用。
   */
  findActiveSceneNarration(input: {
    userId: string;
    courseId: string;
    sceneId: string;
  }): JobRow | null {
    const row = this.#db.prepare(
      `SELECT id, user_id, course_id, kind, mode, input_json, status, progress, attempts,
              error_code, artifact_id, scene_id, narration_hash, created_at, updated_at,
              started_at, finished_at, cancelled_at
         FROM jobs
        WHERE user_id = ? AND course_id = ? AND scene_id = ? AND kind = 'tts'
          AND status IN ('queued', 'running')
        ORDER BY created_at DESC, id DESC LIMIT 1`,
    ).get(input.userId, input.courseId, input.sceneId) as JobRow | undefined;
    return row ?? null;
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
