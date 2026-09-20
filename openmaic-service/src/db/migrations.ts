/**
 * Versioned schema migrations for the service-owned SQLite database.
 *
 * Migrations are append-only and applied in a single transaction. A migration
 * that has already been recorded is never re-run, so `CREATE TABLE` statements
 * stay plain (no `IF NOT EXISTS` safety net that would hide a bad ordering).
 */
export interface Migration {
  version: number;
  name: string;
  statements: string[];
}

export const MIGRATIONS: Migration[] = [
  {
    version: 1,
    name: 'consumed_service_assertions',
    statements: [
      `CREATE TABLE consumed_service_assertions (
         jti TEXT PRIMARY KEY,
         issuer TEXT NOT NULL,
         audience TEXT NOT NULL,
         subject TEXT NOT NULL,
         course_id TEXT NOT NULL,
         scopes TEXT NOT NULL,
         issued_at INTEGER NOT NULL,
         expires_at INTEGER NOT NULL,
         consumed_at INTEGER NOT NULL
       )`,
      `CREATE INDEX idx_consumed_service_assertions_expires_at
         ON consumed_service_assertions (expires_at)`,
    ],
  },
  {
    version: 2,
    name: 'workspaces_stages_and_idempotency',
    statements: [
      // A workspace is the unit a student names and returns to; a stage is one
      // versioned document inside it. `course_id` and `user_id` are denormalized
      // onto both rows on purpose: every read filters by both, and a join to
      // recover them would be a place for an ownership check to go missing.
      `CREATE TABLE workspaces (
         id TEXT PRIMARY KEY,
         user_id TEXT NOT NULL,
         course_id TEXT NOT NULL,
         name TEXT NOT NULL,
         description TEXT NOT NULL DEFAULT '',
         revision INTEGER NOT NULL DEFAULT 1,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL,
         deleted_at TEXT
       )`,
      // Keyset pagination walks (updated_at, id) descending, so the index order
      // matches the query order and the list never re-sorts in memory.
      `CREATE INDEX idx_workspaces_owner_page
         ON workspaces (user_id, course_id, deleted_at, updated_at DESC, id DESC)`,
      `CREATE TABLE stages (
         id TEXT PRIMARY KEY,
         workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
         user_id TEXT NOT NULL,
         course_id TEXT NOT NULL,
         title TEXT NOT NULL,
         document TEXT NOT NULL,
         dsl_version TEXT NOT NULL,
         revision INTEGER NOT NULL DEFAULT 1,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL,
         deleted_at TEXT
       )`,
      `CREATE INDEX idx_stages_workspace_page
         ON stages (user_id, course_id, workspace_id, deleted_at, updated_at DESC, id DESC)`,
      // Idempotency is scoped to the caller and the route: the same key from a
      // different user, or against a different path, is a different operation.
      `CREATE TABLE idempotency_keys (
         key TEXT NOT NULL,
         user_id TEXT NOT NULL,
         course_id TEXT NOT NULL,
         method TEXT NOT NULL,
         path TEXT NOT NULL,
         request_hash TEXT NOT NULL,
         status INTEGER NOT NULL,
         response_body TEXT NOT NULL,
         created_at INTEGER NOT NULL,
         PRIMARY KEY (user_id, key)
       )`,
      `CREATE INDEX idx_idempotency_keys_created_at ON idempotency_keys (created_at)`,
    ],
  },
  {
    version: 3,
    name: 'folders_and_workspace_filing',
    statements: [
      // A folder is a user-visible grouping inside one course. `parent_id` is a
      // self-reference so a tree needs no second table; the route layer refuses
      // cycles, because a cycle would make an "all descendants" walk non-total.
      `CREATE TABLE folders (
         id TEXT PRIMARY KEY,
         user_id TEXT NOT NULL,
         course_id TEXT NOT NULL,
         parent_id TEXT REFERENCES folders(id),
         name TEXT NOT NULL,
         revision INTEGER NOT NULL DEFAULT 1,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL,
         deleted_at TEXT
       )`,
      `CREATE INDEX idx_folders_owner_page
         ON folders (user_id, course_id, deleted_at, updated_at DESC, id DESC)`,
      `CREATE INDEX idx_folders_parent ON folders (user_id, course_id, parent_id)`,
      // Compatibility migration: the column is added to the existing table
      // rather than the table being rebuilt, so an already-deployed database
      // keeps every workspace. Existing rows read back as `NULL` = "unfiled",
      // which is exactly the pre-folder behaviour.
      `ALTER TABLE workspaces ADD COLUMN folder_id TEXT REFERENCES folders(id)`,
      `CREATE INDEX idx_workspaces_folder
         ON workspaces (user_id, course_id, folder_id, deleted_at, updated_at DESC, id DESC)`,
      // Search filters on these columns; without the indexes the keyword scan is
      // fine at demo size but degrades as a student accumulates stages.
      `CREATE INDEX idx_workspaces_updated ON workspaces (user_id, course_id, deleted_at, updated_at DESC, id DESC)`,
      `CREATE INDEX idx_stages_updated ON stages (user_id, course_id, deleted_at, updated_at DESC, id DESC)`,
    ],
  },
  {
    version: 4,
    name: 'materials',
    statements: [
      // A material is one course-scoped document a student brought in. The
      // digest is stored instead of the bytes: what a later stage cites is the
      // extracted text, and the digest is what turns re-uploading the same file
      // into the same material rather than a duplicate row.
      `CREATE TABLE materials (
         id TEXT PRIMARY KEY,
         user_id TEXT NOT NULL,
         course_id TEXT NOT NULL,
         filename TEXT NOT NULL,
         media_type TEXT NOT NULL,
         byte_size INTEGER NOT NULL,
         sha256 TEXT NOT NULL,
         extraction_status TEXT NOT NULL,
         text_content TEXT NOT NULL DEFAULT '',
         revision INTEGER NOT NULL DEFAULT 1,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL,
         deleted_at TEXT
       )`,
      `CREATE INDEX idx_materials_owner_page
         ON materials (user_id, course_id, deleted_at, updated_at DESC, id DESC)`,
      // Partial on purpose: a soft-deleted row must not block re-uploading the
      // same file, which is a new material as far as the student is concerned.
      `CREATE UNIQUE INDEX idx_materials_owner_digest
         ON materials (user_id, course_id, sha256) WHERE deleted_at IS NULL`,
    ],
  },
  {
    version: 5,
    name: 'jobs_and_artifacts',
    statements: [
      `CREATE TABLE jobs (
         id TEXT PRIMARY KEY,
         user_id TEXT NOT NULL,
         course_id TEXT NOT NULL,
         kind TEXT NOT NULL,
         mode TEXT NOT NULL,
         input_json TEXT NOT NULL,
         status TEXT NOT NULL,
         progress INTEGER NOT NULL DEFAULT 0,
         attempts INTEGER NOT NULL DEFAULT 0,
         error_code TEXT,
         artifact_id TEXT,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL,
         started_at TEXT,
         finished_at TEXT,
         cancelled_at TEXT,
         FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
       )`,
      `CREATE INDEX idx_jobs_owner_page
         ON jobs (user_id, course_id, updated_at DESC, id DESC)`,
      `CREATE TABLE artifacts (
         id TEXT PRIMARY KEY,
         job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
         user_id TEXT NOT NULL,
         course_id TEXT NOT NULL,
         filename TEXT NOT NULL,
         media_type TEXT NOT NULL,
         byte_size INTEGER NOT NULL,
         sha256 TEXT NOT NULL,
         payload BLOB NOT NULL,
         created_at TEXT NOT NULL
       )`,
      `CREATE INDEX idx_artifacts_owner ON artifacts (id, user_id, course_id)`,
    ],
  },
  {
    version: 6,
    name: 'material_payloads',
    statements: [
      `ALTER TABLE materials ADD COLUMN payload BLOB`,
    ],
  },
  {
    version: 7,
    name: 'scene_narration_binding',
    statements: [
      // 讲解音频必须**可归属到具体场景**。没有这两列时，"这个 artifact 是哪一页的"
      // 只能靠时间顺序猜，于是切换场景或重复生成后音频就会挂错页——这正是要修的
      // 那个缺陷。scene_id 允许为空：圆桌讨论、视频导出等非讲解任务不绑定场景。
      `ALTER TABLE jobs ADD COLUMN scene_id TEXT`,
      // 讲稿指纹：同一场景、同一讲稿的重复请求可以被识别出来，避免重复计费的
      // MiMo 调用。空值表示该任务与讲稿无关。
      `ALTER TABLE jobs ADD COLUMN narration_hash TEXT`,
      // 按 (用户, 课程, 场景) 查"这一页有没有现成音频"是最热的一条读路径。
      `CREATE INDEX idx_jobs_scene_narration
         ON jobs (user_id, course_id, scene_id, kind, status)`,
    ],
  },
];

export const SCHEMA_VERSION = MIGRATIONS.reduce((max, item) => Math.max(max, item.version), 0);
