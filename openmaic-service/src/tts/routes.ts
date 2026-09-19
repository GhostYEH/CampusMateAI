import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';

export const TTS_SCOPE = 'tts:write';
export const TTS_CAPABILITY: Capability = 'tts';

function parseBody(request: RouteRequest): Record<string, unknown> {
  if (!request.body || request.body.length === 0) throw new WorkspaceError('invalid_request', 'request body is required');
  let value: unknown;
  try { value = JSON.parse(request.body.toString('utf8')); } catch { throw new WorkspaceError('invalid_request', 'request body is not valid JSON'); }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new WorkspaceError('invalid_request', 'request body must be an object');
  return value as Record<string, unknown>;
}

function requiredText(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) throw new WorkspaceError('invalid_request', 'text is required');
  if (value.trim().length > 20_000) throw new WorkspaceError('invalid_request', 'text is too long');
  return value.trim();
}

export function createTtsRoutes(options: { database: ServiceDatabase; available?: boolean }): RouteDefinition[] {
  const available = options.available ?? false;
  return [{
    method: 'POST', pattern: '/internal/courses/:courseId/tts', scopes: [TTS_SCOPE], courseScoped: true, capabilities: [TTS_CAPABILITY],
    handler: (request): RouteResponse => {
      try {
        requiredText(parseBody(request).text);
        if (!available) return { status: 503, body: { error: 'provider_unavailable', message: 'tts provider is unavailable' } };
        return { status: 503, body: { error: 'provider_unavailable', message: 'tts provider is unavailable' } };
      } catch (error) {
        if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
        throw error;
      }
    },
  }];
}
