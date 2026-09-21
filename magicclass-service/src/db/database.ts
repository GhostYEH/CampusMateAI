import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

import { MIGRATIONS, SCHEMA_VERSION } from './migrations.ts';

/**
 * A SQLite handle plus the transaction helper every write path must use.
 *
 * `node:sqlite` has no nested transactions, so `transaction()` is re-entrant by
 * depth: an inner call joins the outer transaction instead of issuing a nested
 * `BEGIN`, which keeps "consume the assertion jti" and "apply the idempotent
 * write" in one atomic unit.
 */
export class ServiceDatabase {
  readonly #db: DatabaseSync;
  #depth = 0;

  constructor(path: string) {
    if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true });
    this.#db = new DatabaseSync(path);
    this.#db.exec('PRAGMA journal_mode = WAL');
    this.#db.exec('PRAGMA foreign_keys = ON');
    this.#db.exec('PRAGMA busy_timeout = 5000');
    migrate(this.#db);
  }

  get raw(): DatabaseSync {
    return this.#db;
  }

  transaction<T>(work: () => T): T {
    if (this.#depth > 0) return work();
    this.#db.exec('BEGIN IMMEDIATE');
    this.#depth += 1;
    try {
      const result = work();
      this.#db.exec('COMMIT');
      return result;
    } catch (error) {
      try {
        this.#db.exec('ROLLBACK');
      } catch {
        // A failed rollback must not mask the original failure.
      }
      throw error;
    } finally {
      this.#depth -= 1;
    }
  }

  close() {
    this.#db.close();
  }
}

export function migrate(db: DatabaseSync) {
  db.exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at INTEGER NOT NULL
  )`);
  const applied = new Set(
    db.prepare('SELECT version FROM schema_migrations').all().map((row) => Number(row.version)),
  );
  const record = db.prepare('INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)');
  for (const migration of MIGRATIONS) {
    if (applied.has(migration.version)) continue;
    db.exec('BEGIN IMMEDIATE');
    try {
      for (const statement of migration.statements) db.exec(statement);
      record.run(migration.version, migration.name, Date.now());
      db.exec('COMMIT');
    } catch (error) {
      try {
        db.exec('ROLLBACK');
      } catch {
        // Preserve the original migration failure.
      }
      throw error;
    }
  }
}

export { SCHEMA_VERSION };
