import { isAbsolute, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export interface ServiceConfig {
  host: string;
  port: number;
  databasePath: string;
  internalSecret: string;
  /**
   * Origin of the external 3D/CDN capability, if the deployment has one.
   * `undefined` is a real answer: without it `visualization3d` scenes degrade
   * explicitly instead of rendering blank.
   */
  externalCdnUrl?: string;
  /**
   * OpenAI-compatible chat-completions endpoint used for content generation
   * and multi-agent discussion. Absent means the service degrades truthfully:
   * generation falls back to the local template and discussion reports
   * provider_unavailable.
   */
  provider?: ProviderConfig;
  /** Speech synthesis endpoint (MiMo V2.5 TTS). Absent means tts is unavailable. */
  tts?: TtsConfig;
}

export interface ProviderConfig {
  /** Includes the version prefix, e.g. `https://provider.example/v1`. */
  baseUrl: string;
  apiKey: string;
  model: string;
  timeoutMs: number;
}

export interface TtsConfig extends ProviderConfig {
  /** Preset voice id, e.g. `苏打`. */
  voice: string;
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

/**
 * Load a local `.env` file (KEY=VALUE lines) into `env` without ever
 * overriding a variable the caller already set. Provider credentials live
 * here so they never have to appear in shell history or in a tracked file.
 */
export function loadDotEnv(env: Record<string, string | undefined> = process.env, serviceRoot = SERVICE_ROOT): void {
  let text: string;
  try {
    text = readFileSync(resolve(serviceRoot, '.env'), 'utf8');
  } catch {
    return;
  }
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const separator = line.indexOf('=');
    if (separator <= 0) continue;
    const key = line.slice(0, separator).trim();
    if (!key || Object.hasOwn(env, key)) continue;
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
}

/**
 * Parse an optional OpenAI-compatible endpoint. Both halves must be present
 * together: a URL without a key (or the reverse) is a deployment mistake that
 * would only surface as a mysterious 401 later, so it fails at startup.
 */
function readEndpoint(
  env: Record<string, string | undefined>,
  prefix: string,
  options: { defaultModel?: string; defaultTimeoutSeconds: number; maxTimeoutSeconds?: number },
): { baseUrl: string; apiKey: string; model: string; timeoutMs: number } | undefined {
  const baseUrl = optionalEndpointUrl(env[`${prefix}_BASE_URL`], `${prefix}_BASE_URL`);
  const apiKey = (env[`${prefix}_API_KEY`] ?? '').trim();
  if (!baseUrl && !apiKey) return undefined;
  if (!baseUrl || !apiKey) {
    throw new ConfigError(`${prefix}_BASE_URL and ${prefix}_API_KEY must be configured together`);
  }
  const model = (env[`${prefix}_MODEL`] ?? '').trim() || options.defaultModel || '';
  if (!model) throw new ConfigError(`${prefix}_MODEL is required when ${prefix}_BASE_URL is configured`);
  const maxSeconds = options.maxTimeoutSeconds ?? 600;
  const rawTimeout = (env[`${prefix}_TIMEOUT_SECONDS`] ?? '').trim();
  let timeoutMs = options.defaultTimeoutSeconds * 1000;
  if (rawTimeout) {
    const parsed = Number(rawTimeout);
    if (!Number.isFinite(parsed) || parsed <= 0 || parsed > maxSeconds) {
      throw new ConfigError(`${prefix}_TIMEOUT_SECONDS must be a number between 1 and ${maxSeconds}`);
    }
    timeoutMs = parsed * 1000;
  }
  return { baseUrl, apiKey, model, timeoutMs };
}

function optionalEndpointUrl(value: string | undefined, name: string): string {
  const text = (value ?? '').trim();
  if (!text) return '';
  let url: URL;
  try {
    url = new URL(text);
  } catch {
    throw new ConfigError(`${name} must be a valid URL`);
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') {
    throw new ConfigError(`${name} must use http(s)`);
  }
  // Credentials inside the URL would leak into logs; the key travels in the
  // Authorization header only.
  if (url.username || url.password) throw new ConfigError(`${name} must not embed credentials`);
  if (url.search || url.hash) throw new ConfigError(`${name} must not carry a query or fragment`);
  return text.replace(/\/+$/, '');
}

function readTtsVoice(value: string | undefined): string {
  const voice = (value ?? '').trim();
  if (voice.length > 80) throw new ConfigError('OPENMAIC_TTS_VOICE must be at most 80 characters');
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f]/.test(voice)) throw new ConfigError('OPENMAIC_TTS_VOICE must not contain control characters');
  return voice || '苏打';
}

export function loadConfig(env = process.env): ServiceConfig {
  const internalSecret = (env.OPENMAIC_INTERNAL_SECRET ?? '').trim();
  if (!internalSecret) {
    // Fail closed: an unauthenticated internal service is worse than no service.
    throw new ConfigError('OPENMAIC_INTERNAL_SECRET is required');
  }
  const externalCdnUrl = (env.OPENMAIC_EXTERNAL_CDN_URL ?? '').trim();
  const provider = readEndpoint(env, 'OPENMAIC_PROVIDER', { defaultTimeoutSeconds: 120 });
  const ttsEndpoint = readEndpoint(env, 'OPENMAIC_TTS', {
    defaultModel: 'mimo-v2.5-tts',
    defaultTimeoutSeconds: 180,
    maxTimeoutSeconds: 600,
  });
  const tts: TtsConfig | undefined = ttsEndpoint ? { ...ttsEndpoint, voice: readTtsVoice(env.OPENMAIC_TTS_VOICE) } : undefined;
  return {
    host: (env.OPENMAIC_HOST ?? '').trim() || '127.0.0.1',
    port: positiveInteger(env.OPENMAIC_PORT, 4010),
    databasePath: resolveDatabasePath(env.OPENMAIC_DATABASE_URL),
    internalSecret,
    ...(externalCdnUrl ? { externalCdnUrl } : {}),
    ...(provider ? { provider } : {}),
    ...(tts ? { tts } : {}),
  };
}
