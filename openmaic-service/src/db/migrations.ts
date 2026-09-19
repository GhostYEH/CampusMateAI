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
];

export const SCHEMA_VERSION = MIGRATIONS.reduce((max, item) => Math.max(max, item.version), 0);
