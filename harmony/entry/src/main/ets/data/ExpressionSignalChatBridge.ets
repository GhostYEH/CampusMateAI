import { ChatRequest, ExpressionSignalRequest } from './Models';
import { StableExpressionSignal } from '../service/ExpressionSignalProcessor';

/** Adds a stable signal to a chat request while preserving the existing DTO contract. */
export function withExpressionSignal(request: ChatRequest, signal: StableExpressionSignal | undefined): ChatRequest {
  if (signal === undefined || !signal.isStable) return request;
  const expressionSignal: ExpressionSignalRequest = {
    label: signal.label,
    confidence: signal.confidence,
    is_stable: true,
    timestamp: signal.timestamp,
    model_version: signal.modelVersion
  };
  return {
    message: request.message,
    session_id: request.session_id,
    stream: request.stream,
    expression_signal: expressionSignal
  };
}
