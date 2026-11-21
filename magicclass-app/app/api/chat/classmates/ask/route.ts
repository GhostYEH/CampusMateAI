import type { NextRequest } from 'next/server';
import { callLLM } from '@/lib/ai/llm';
import { isProviderKeyRequired } from '@/lib/ai/providers';
import { createLogger } from '@/lib/logger';
import { apiError, apiSuccess } from '@/lib/server/api-response';
import {
  buildClassmateAnswerPrompt,
  classmateTokens,
  ClassmateRequestError,
  parseClassmateAnswer,
  readClassmateBody,
  validateClassmateQuestion,
} from '@/lib/server/classmate-participation';
import { resolveModelFromRequest } from '@/lib/server/resolve-model';

export const maxDuration = 60;
const log = createLogger('Classmate Ask API');

/** Answering one direct question is smaller than a page reaction, and must not stall the lesson. */
const ASK_TIMEOUT_MS = 45_000;

export async function POST(req: NextRequest) {
  const signal = AbortSignal.any([req.signal, AbortSignal.timeout(ASK_TIMEOUT_MS)]);
  try {
    const body = await readClassmateBody(req, signal);
    const { request, agent, question } = validateClassmateQuestion(body);
    const { model, providerId, apiKey, thinkingConfig } = await resolveModelFromRequest(req, body);
    if (isProviderKeyRequired(providerId) && !apiKey) {
      return apiError('MISSING_API_KEY', 401, 'API Key is required');
    }
    signal.throwIfAborted();

    const result = await callLLM(
      {
        model,
        ...buildClassmateAnswerPrompt({ request, agent, question }),
        abortSignal: signal,
        maxOutputTokens: 900,
        maxRetries: 0,
      },
      'chat-adapter',
      undefined,
      thinkingConfig,
    );
    signal.throwIfAborted();
    log.info('Classmate answered a direct question', {
      agentId: agent.id,
      sceneId: request.scene.id,
    });
    return apiSuccess({
      message: { agentId: agent.id, text: parseClassmateAnswer(result.text) },
      usage: { tokens: classmateTokens(result) },
    });
  } catch (error) {
    if (req.signal.aborted)
      return apiError('GENERATION_FAILED', 499, 'Classmate request was aborted');
    if (error instanceof ClassmateRequestError) {
      return apiError('INVALID_REQUEST', error.status, error.message);
    }
    if (error instanceof Error && ['AbortError', 'TimeoutError'].includes(error.name)) {
      return apiError('GENERATION_FAILED', 504, 'Classmate answer timed out');
    }
    log.error('Classmate answer failed', error);
    return apiError('GENERATION_FAILED', 502, 'Failed to generate a classmate answer');
  }
}
