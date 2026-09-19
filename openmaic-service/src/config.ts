import { isAbsolute, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export interface ServiceConfig {
  host: string;
  port: number;
  databasePath: string;
  internalSecret: string;
}

/** Raised when the process cannot start with the supplied environment. */
export class ConfigError extends Error {}

/**
 * Root of the `openmaic-service` package, derived from this module's URL so the
 * service never depends on the caller's working directory or on a machine
 * specific absolute path.
 */
export const SERVICE_ROOT = fileURLToPath(new URL('..', import.meta.url));

function positiveInteger(value: string | undefined, fallback: number) {
  const parsed = Number(value ?? fallback);
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) {
    throw new ConfigError('OPENMAIC_PORT must be a valid TCP port');
  }
  return parsed;
}

/**
 * Resolve the SQLite location. The service owns its own database; a networked
 * database URL would silently turn "persisted" into "unavailable", so anything
 * that is not a local file path is rejected instead of guessed at.
 */
export function resolveDatabasePath(raw: string | undefined, serviceRoot = SERVICE_ROOT) {
  const value = (raw ?? '').trim();
  if (!value) throw new ConfigError('OPENMAIC_DATABASE_URL is required');
  // SQLite's in-memory database is not a path and must not be resolved against
  // the service root; it is mainly used by tests.
  if (value === ':memory:') return value;
  const withoutScheme = value.replace(/^(sqlite|file):(\/\/)?/i, '');
  // A single-letter prefix is a Windows drive, not a URL scheme, so only reject
  // prefixes of two or more characters (`postgres:`, `mysql:`, `https:` ...).
  const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(withoutScheme);
  if (scheme && scheme[1].length > 1) {
    throw new ConfigError('OPENMAIC_DATABASE_URL must point to a local SQLite file');
  }
  return isAbsolute(withoutScheme) ? withoutScheme : resolve(serviceRoot, withoutScheme);
}

export function loadConfig(env = process.env): ServiceConfig {
  const internalSecret = (env.OPENMAIC_INTERNAL_SECRET ?? '').trim();
  if (!internalSecret) {
    // Fail closed: an unauthenticated internal service is worse than no service.
    throw new ConfigError('OPENMAIC_INTERNAL_SECRET is required');
  }
  return {
    host: (env.OPENMAIC_HOST ?? '').trim() || '127.0.0.1',
    port: positiveInteger(env.OPENMAIC_PORT, 4010),
    databasePath: resolveDatabasePath(env.OPENMAIC_DATABASE_URL),
    internalSecret,
  };
}
