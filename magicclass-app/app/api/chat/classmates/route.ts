import { NextRequest } from 'next/server';
import { callLLM } from '@/lib/ai/llm';
import { isProviderKeyRequired } from '@/lib/ai/providers';
import { createLogger } from '@/lib/logger';
import { apiError, apiSuccess } from '@/lib/server/api-response';
import {
  buildClassmatePrompt,
  buildClassmateRoutingPrompt,
  ClassmateRequestError,
  classmateTokens,
  fallbackClassmates,
  parseClassmateMessages,
  parseClassmateRouting,
  readClassmateBody,
  selectClassmates,
  validateClassmateRequest,
  type ClassmateRequest,
} from '@/lib/server/classmate-participation';
import { resolveModelFromRequest } from '@/lib/server/resolve-model';

export const maxDuration = 60;
const log = createLogger('Classmate Chat API');

/** The overall budget for the whole request; the page must answer inside it. */
const OVERALL_TIMEOUT_MS = 55_000;
/** The routing step is small and cheap; it must not eat the speaking step's budget. */
const ROUTING_TIMEOUT_MS = 8_000;

/**
 * Decide who speaks. A failed routing step falls back to the roster rotation
 * instead of failing the page: the classroom keeps a single voice, and our own
 * rule never fabricates dialogue.
 */
async function decideSpeakers(args: {
  model: string;
  request: ClassmateRequest;
  signal: AbortSignal;
  thinkingConfig: Parameters<typeof callLLM>[3];
}) {
  const { model, request, signal, thinkingConfig } = args;
  try {
    const result = await callLLM(
      {
        model,
        ...buildClassmateRoutingPrompt(request),
        abortSignal: AbortSignal.any([signal, AbortSignal.timeout(ROUTING_TIMEOUT_MS)]),
        maxOutputTokens: 600,
        maxRetries: 0,
      },
      'chat-adapter',
      undefined,
      thinkingConfig,
    );
    const tokens = classmateTokens(result);
    const routing = parseClassmateRouting(result.text, request.agents);
    if (!routing) {
      return {
        selected: fallbackClassmates(request),
        needs: null,
        by: 'fallback' as const,
        tokens,
      };
    }
    return {
      selected: selectClassmates(request, routing),
      needs: routing.needs,
      by: 'router' as const,
      tokens,
    };
  } catch (error) {
    if (signal.aborted) throw error;
    return {
      selected: fallbackClassmates(request),
      needs: null,
      by: 'fallback' as const,
      tokens: 0,
    };
  }
}

export async function POST(req: NextRequest) {
  const signal = AbortSignal.any([req.signal, AbortSignal.timeout(OVERALL_TIMEOUT_MS)]);
  try {
    const body = await readClassmateBody(req, signal);
    const request = validateClassmateRequest(body);
    if (request.agents.length === 0) {
      return apiSuccess({
        messages: [],
        routed: { selected: [], needs: null, by: 'silence' },
        usage: { tokens: 0 },
      });
    }
    const { model, providerId, apiKey, thinkingConfig } = await resolveModelFromRequest(
      req,
      body,
      'chat-adapter',
    );
    if (isProviderKeyRequired(providerId) && !apiKey) {
      return apiError('MISSING_API_KEY', 401, 'API Key is required');
    }
    signal.throwIfAborted();

    const routed = await decideSpeakers({ model, request, signal, thinkingConfig });
    const selected = request.agents.filter((agent) => routed.selected.includes(agent.id));
    if (selected.length === 0) {
      return apiSuccess({
        messages: [],
        routed: { selected: [], needs: routed.needs, by: 'silence' },
        usage: { tokens: routed.tokens },
      });
    }

    signal.throwIfAborted();
    const result = await callLLM(
      {
        model,
        ...buildClassmatePrompt(request, selected),
        abortSignal: signal,
        maxOutputTokens: 2400,
        maxRetries: 0,
      },
      'chat-adapter',
      undefined,
      thinkingConfig,
    );
    signal.throwIfAborted();
    return apiSuccess({
      messages: parseClassmateMessages(result.text, selected),
      routed: { selected: selected.map((agent) => agent.id), needs: routed.needs, by: routed.by },
      usage: { tokens: routed.tokens + classmateTokens(result) },
    });
  } catch (error) {
    if (req.signal.aborted)
      return apiError('GENERATION_FAILED', 499, 'Classmate request was aborted');
    if (signal.aborted) return apiError('GENERATION_FAILED', 504, 'Classmate generation timed out');
    if (error instanceof ClassmateRequestError) {
      return apiError('INVALID_REQUEST', error.status, error.message);
    }
    log.error('Classmate generation failed:', error);
    return apiError(
      'GENERATION_FAILED',
      502,
      error instanceof Error ? error.message : 'Classmate generation failed',
    );
  }
}
