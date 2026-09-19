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
];

export const SCHEMA_VERSION = MIGRATIONS.reduce((max, item) => Math.max(max, item.version), 0);
