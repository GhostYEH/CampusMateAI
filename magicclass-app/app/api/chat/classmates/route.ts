import { NextRequest } from 'next/server';
import { callLLM } from '@/lib/ai/llm';
import { isProviderKeyRequired } from '@/lib/ai/providers';
import { apiError, apiSuccess } from '@/lib/server/api-response';
import {
  buildClassmatePrompt,
  ClassmateRequestError,
  parseClassmateMessages,
  readClassmateBody,
  validateClassmateRequest,
} from '@/lib/server/classmate-participation';
import { resolveModelFromRequest } from '@/lib/server/resolve-model';

export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const signal = AbortSignal.any([req.signal, AbortSignal.timeout(55_000)]);
  try {
    const body = await readClassmateBody(req, signal);
    const request = validateClassmateRequest(body);
    if (request.agents.length === 0) return apiSuccess({ messages: [] });
    const { model, providerId, apiKey, thinkingConfig } = await resolveModelFromRequest(
      req,
      body,
      'chat-adapter',
    );
    if (isProviderKeyRequired(providerId) && !apiKey) {
      return apiError('MISSING_API_KEY', 401, 'API Key is required');
    }
    signal.throwIfAborted();
    const result = await callLLM(
      {
        model,
        ...buildClassmatePrompt(request),
        abortSignal: signal,
        maxOutputTokens: 2400,
        maxRetries: 0,
      },
      'chat-adapter',
      undefined,
      thinkingConfig,
    );
    signal.throwIfAborted();
    return apiSuccess({ messages: parseClassmateMessages(result.text, request.agents) });
  } catch (error) {
    if (req.signal.aborted)
      return apiError('GENERATION_FAILED', 499, 'Classmate request was aborted');
    if (signal.aborted) return apiError('GENERATION_FAILED', 504, 'Classmate generation timed out');
    if (error instanceof ClassmateRequestError) {
      return apiError('INVALID_REQUEST', error.status, error.message);
    }
    return apiError(
      'GENERATION_FAILED',
      502,
      error instanceof Error ? error.message : 'Classmate generation failed',
    );
  }
}
