import type { StatementSync } from 'node:sqlite';

import type { ConsumedAssertionRecord, ReplayStore } from '../serviceAssertion.ts';
import { ServiceAssertionError } from '../serviceAssertion.ts';
import type { ServiceDatabase } from './database.ts';

/**
 * Durable jti consumption.
 *
 * The in-process map the service started with lost every record on restart, so a
 * captured assertion could be replayed against a freshly booted process. This
 * store keeps the record in the service database and participates in whatever
 * transaction the caller opened, so "this assertion was used" commits atomically
 * with the idempotent write it authorised.
 */
export class SqliteReplayStore implements ReplayStore {
  readonly #insert: StatementSync;
  readonly #prune: StatementSync;

  constructor(db: ServiceDatabase) {
    this.#insert = db.raw.prepare(`INSERT INTO consumed_service_assertions (
        jti, issuer, audience, subject, course_id, scopes, issued_at, expires_at, consumed_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(jti) DO NOTHING`);
    this.#prune = db.raw.prepare('DELETE FROM consumed_service_assertions WHERE expires_at <= ?');
  }

  consume(record: ConsumedAssertionRecord) {
    this.#prune.run(record.consumedAt);
    const result = this.#insert.run(
      record.jti,
      record.issuer,
      record.audience,
      record.subject,
      record.courseId,
      JSON.stringify(record.scopes),
      record.issuedAt,
      record.expiresAt,
      record.consumedAt,
    );
    if (Number(result.changes) === 0) {
      throw new ServiceAssertionError('assertion replay detected');
    }
  }

  /** Drop records whose assertion window has closed. Safe to call periodically. */
  pruneExpired(now: number): number {
    return Number(this.#prune.run(now).changes);
  }
}
