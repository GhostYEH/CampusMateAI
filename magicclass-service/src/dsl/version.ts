/**
 * DSL version + migration registry — ported from `@magicclass/dsl` v1.0.3
 * (`packages/@magicclass/dsl/src/version.ts`), MIT.
 *
 * The DSL version is independent of any package version: it identifies the shape
 * of the *serialized* document so persisted stages can be migrated forward as
 * the schema evolves.
 *
 * Two version lines exist and they are mechanically disjoint — the document line
 * stamps `dslVersion`, the runtime line stamps `runtimeDslVersion`. Disjoint keys
 * are necessary but not sufficient: an object carrying only the *other* line's
 * stamp must not be walked by this line's ladder, because that would stamp a
 * foreign field and, once a real transform lands, mangle the payload. The
 * cross-line guard in {@link runLadder} throws instead of guessing.
 *
 * Ported subset (documented as such in `docs/magicclass-capability-matrix.md`):
 * the ladder mechanism, the cross-line guard, the version comparison, and the
 * three shipped migrations. The upstream runtime-session shape is not ported —
 * only its *version line mechanism* is, because this service needs a place to
 * stamp its own runtime aggregates without colliding with the document line.
 */

import { stripLegacyLineGeometry } from './legacyLineGeometry.ts';

/** Current version of the serialized document contract. */
export const DSL_VERSION = '0.3.0';
export type DslVersion = typeof DSL_VERSION;

/**
 * The version a document is treated as when it carries no `dslVersion` stamp:
 * everything written before the version field existed. The first ladder entry
 * lifts these legacy documents forward.
 */
export const UNVERSIONED_DSL_VERSION = '0.0.0';

/**
 * The first shipped serialized-contract version — a **pinned literal**, not the
 * moving {@link DSL_VERSION}. Migration endpoints must be immutable: they name a
 * fixed point in the ladder.
 */
export const INITIAL_DSL_VERSION = '0.1.0';

/** Envelope property carrying the serialized-contract version on a document. */
export const DSL_VERSION_KEY = 'dslVersion';

/** Envelope property carrying the serialized-contract version on a runtime aggregate. */
export const RUNTIME_DSL_VERSION_KEY = 'runtimeDslVersion';

/** Current version of the serialized runtime contract. */
export const RUNTIME_DSL_VERSION = '0.1.0';

export interface DslVersioned {
  dslVersion?: string;
}

export interface RuntimeVersioned {
  runtimeDslVersion?: string;
}

export interface DslMigration {
  from: string;
  to: string;
  migrate: (doc: unknown) => unknown;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Numeric, segment-wise comparison of dotted versions.
 *
 * Missing segments count as 0, so `1.0` and `1.0.0` compare equal. Non-numeric
 * segments are rejected by {@link versionOf} before reaching here.
 */
export function compareVersions(left: string, right: string): number {
  const a = left.split('.').map(Number);
  const b = right.split('.').map(Number);
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    const x = a[index] ?? 0;
    const y = b[index] ?? 0;
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

const VERSION_PATTERN = /^\d+(\.\d+)*$/;

function isVersion(value: unknown): value is string {
  return typeof value === 'string' && VERSION_PATTERN.test(value);
}

/** Thrown when an aggregate carries the *other* version line's stamp, or none where one is required. */
export class DslVersionError extends Error {
  readonly code: 'cross_line' | 'no_runtime_epoch' | 'malformed_version' | 'no_path' | 'stuck';

  constructor(code: DslVersionError['code'], message: string) {
    super(message);
    this.name = 'DslVersionError';
    this.code = code;
  }
}

function crossLineError(key: string, otherKey: string): DslVersionError {
  return new DslVersionError(
    'cross_line',
    `dsl: envelope carries "${otherKey}" but not "${key}"; refusing to walk the wrong version line`,
  );
}

function noRuntimeEpochError(key: string): DslVersionError {
  return new DslVersionError(
    'no_runtime_epoch',
    `dsl: aggregate has no "${key}" stamp and the runtime line has no unversioned epoch`,
  );
}

/**
 * Read the version stamp off an envelope, applying the cross-line guard.
 *
 * Three cases, all enforced in this one reader so the runner, its predicate and
 * the plain `*VersionOf` readers agree on every envelope:
 * 1. own stamp present → use it (must be well-formed);
 * 2. own stamp absent, sibling stamp absent → the line's legacy version (or, on
 *    a line with no unversioned epoch, throw);
 * 3. own stamp absent, sibling stamp present → throw; neither silent answer is
 *    safe (walking would mangle the payload, returning unchanged would orphan it
 *    from its own line forever).
 */
export function versionOf(
  doc: unknown,
  key: string,
  otherKey: string,
  legacyVersion: string | null,
): string {
  if (!isObject(doc)) return legacyVersion ?? UNVERSIONED_DSL_VERSION;
  const own = doc[key];
  if (own === undefined) {
    if (doc[otherKey] !== undefined) throw crossLineError(key, otherKey);
    if (legacyVersion === null) throw noRuntimeEpochError(key);
    return legacyVersion;
  }
  if (!isVersion(own)) {
    throw new DslVersionError('malformed_version', `dsl: "${key}" is not a dotted version: ${String(own)}`);
  }
  return own;
}

/** Non-throwing variant for readers that only want to report the version. */
export function documentDslVersionOf(doc: unknown): string | null {
  if (!isObject(doc) || !isVersion(doc[DSL_VERSION_KEY])) return null;
  return doc[DSL_VERSION_KEY];
}

function stampVersion(doc: unknown, version: string, key: string): unknown {
  if (!isObject(doc)) return doc;
  return { ...doc, [key]: version };
}

/** True when {@link migrate} would change the document. */
export function needsMigration(doc: unknown): boolean {
  if (!isObject(doc)) return false;
  return compareVersions(versionOf(doc, DSL_VERSION_KEY, RUNTIME_DSL_VERSION_KEY, UNVERSIONED_DSL_VERSION), DSL_VERSION) < 0;
}

/** True when {@link migrateRuntime} would change the aggregate. */
export function needsRuntimeMigration(doc: unknown): boolean {
  if (!isObject(doc)) return false;
  return compareVersions(versionOf(doc, RUNTIME_DSL_VERSION_KEY, DSL_VERSION_KEY, null), RUNTIME_DSL_VERSION) < 0;
}

/**
 * Walk a document from whatever version it was written at up to the target,
 * stamping as it goes.
 *
 * Idempotent, forward-compatible, fail-loud, pure. Non-objects are returned
 * as-is — they are not migratable aggregates.
 */
function runLadder(
  doc: unknown,
  ladder: readonly DslMigration[],
  targetVersion: string,
  key: string,
  otherKey: string,
  legacyVersion: string | null,
): unknown {
  if (!isObject(doc)) return doc;

  let version = versionOf(doc, key, otherKey, legacyVersion);

  // Already current, or written ahead of us — leave the document as-is. A newer
  // document is never "migrated backwards".
  if (compareVersions(version, targetVersion) >= 0) return doc;

  let current: unknown = doc;
  // Guard against a malformed (cyclic / non-advancing) registry so a bad entry
  // can't spin forever.
  for (let step = 0; step < ladder.length + 1; step += 1) {
    if (version === targetVersion) return current;
    const next = ladder.find((migration) => migration.from === version);
    if (!next) {
      throw new DslVersionError('no_path', `dsl: no migration path from "${version}" to "${targetVersion}"`);
    }
    current = stampVersion(next.migrate(current), next.to, key);
    version = next.to;
  }

  throw new DslVersionError('stuck', `dsl: migration ladder did not reach "${targetVersion}" (stuck at "${version}")`);
}

/**
 * Ordered migration ladder. Each entry's `to` is the next entry's `from`, and
 * the last entry's `to` is {@link DSL_VERSION} (both checked by a test). Every
 * `from` / `to` is a pinned literal — never the moving {@link DSL_VERSION} — so
 * appending a future step can't retroactively re-target an existing one.
 */
export const DSL_MIGRATIONS: readonly DslMigration[] = [
  // Stamps legacy (pre-`dslVersion`) documents up to 0.1.0. Intentionally a
  // no-op *transform*: the on-disk shape at that point already was 0.1.0.
  { from: UNVERSIONED_DSL_VERSION, to: INITIAL_DSL_VERSION, migrate: (doc) => doc },
  // 0.2.0 abolished `audioUrl` on speech actions. A pure stamp: only the
  // app-side reference converter may remove the field, because only it can tell
  // a live handle from a dead one.
  { from: INITIAL_DSL_VERSION, to: '0.2.0', migrate: (doc) => doc },
  // First real payload transform: strip the stray `rotate` / `height` fields
  // legacy runtimes could persist onto `line` elements.
  { from: '0.2.0', to: '0.3.0', migrate: stripLegacyLineGeometry },
];

/**
 * The runtime line's ladder. Ships **empty** on purpose: runtime aggregates are
 * born stamped, there is no unversioned epoch to lift, and a no-op first entry
 * would silently accept a misrouted document instead of failing loud.
 */
export const RUNTIME_DSL_MIGRATIONS: readonly DslMigration[] = [];

/** Migrate a document forward to {@link DSL_VERSION}, stamping `dslVersion`. */
export function migrate(doc: unknown): unknown {
  return runLadder(
    doc,
    DSL_MIGRATIONS,
    DSL_VERSION,
    DSL_VERSION_KEY,
    RUNTIME_DSL_VERSION_KEY,
    UNVERSIONED_DSL_VERSION,
  );
}

/**
 * Migrate a runtime aggregate forward to {@link RUNTIME_DSL_VERSION}, stamping
 * `runtimeDslVersion`.
 *
 * **No unversioned epoch**: a wholly-unstamped object here is a misrouted legacy
 * document or an unstamped producer write, and throws.
 */
export function migrateRuntime(doc: unknown): unknown {
  return runLadder(
    doc,
    RUNTIME_DSL_MIGRATIONS,
    RUNTIME_DSL_VERSION,
    RUNTIME_DSL_VERSION_KEY,
    DSL_VERSION_KEY,
    null,
  );
}

/** Stamp a freshly produced runtime aggregate so it never enters the unversioned path. */
export function stampRuntimeVersion<T>(doc: T): T {
  return stampVersion(doc, RUNTIME_DSL_VERSION, RUNTIME_DSL_VERSION_KEY) as T;
}
