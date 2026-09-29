import { APICallError, RetryError } from 'ai';
import { apiError } from '@/lib/server/api-response';

const HTTP_ERROR_MIN = 400;
const HTTP_ERROR_MAX = 599;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function toHttpErrorStatus(value: unknown): number | undefined {
  const parsed =
    typeof value === 'number'
      ? value
      : typeof value === 'string'
        ? Number.parseInt(value, 10)
        : Number.NaN;

  return Number.isInteger(parsed) && parsed >= HTTP_ERROR_MIN && parsed <= HTTP_ERROR_MAX
    ? parsed
    : undefined;
}

function statusFromError(error: unknown, seen = new Set<unknown>()): number | undefined {
  if (!error || seen.has(error)) return undefined;
  seen.add(error);

  if (APICallError.isInstance(error)) {
    return toHttpErrorStatus(error.statusCode);
  }

  if (RetryError.isInstance(error)) {
    return (
      statusFromError(error.lastError, seen) ??
      error.errors
        .map((nested) => statusFromError(nested, seen))
        .find((status): status is number => status !== undefined)
    );
  }

  if (!isRecord(error)) return undefined;

  const status = toHttpErrorStatus(error.statusCode ?? error.status ?? error.status_code);
  if (status !== undefined) return status;

  return statusFromError(error.cause, seen) ?? statusFromError(error.lastError, seen);
}

function retryAfterFromError(error: unknown, seen = new Set<unknown>()): string | undefined {
  if (!error || seen.has(error)) return undefined;
  seen.add(error);
  if (!isRecord(error)) return undefined;

  const headers = error.responseHeaders;
  if (isRecord(headers)) {
    const value = Object.entries(headers).find(([name]) => name.toLowerCase() === 'retry-after')?.[1];
    if (typeof value === 'string') {
      const seconds = Number(value);
      if ((Number.isFinite(seconds) && seconds >= 0) || Number.isFinite(Date.parse(value))) {
        return value;
      }
    }
  }

  return (
    retryAfterFromError(error.lastError, seen) ??
    (Array.isArray(error.errors)
      ? error.errors.map((nested) => retryAfterFromError(nested, seen)).find(Boolean)
      : undefined) ??
    retryAfterFromError(error.cause, seen)
  );
}

function messageForStatus(status: number): string {
  if (status === 401 || status === 403) {
    return 'Upstream authentication or authorization failed.';
  }
  if (status === 404) return 'Upstream endpoint not found.';
  if (status === 429) return 'Upstream rate limit reached. Please try again shortly.';
  if (status >= 500) return 'Upstream model provider is temporarily unavailable. Please try again.';
  return 'Upstream provider rejected the request.';
}

/**
 * Preserve a provider's HTTP semantics for client retry classification without
 * exposing provider response bodies, URLs, or credential-adjacent details.
 */
export function llmApiError(error: unknown) {
  const status = statusFromError(error);
  if (status === undefined) {
    return apiError('INTERNAL_ERROR', 500, 'Scene generation failed. Please try again.');
  }

  const response = apiError(
    status === 429 ? 'RATE_LIMITED' : 'UPSTREAM_ERROR',
    status,
    messageForStatus(status),
  );
  if (status === 429) {
    const retryAfter = retryAfterFromError(error);
    if (retryAfter) response.headers.set('Retry-After', retryAfter);
  }
  return response;
}
