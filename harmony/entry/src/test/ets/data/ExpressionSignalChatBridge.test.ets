import { describe, expect, it } from '@ohos/hypium';
import { withExpressionSignal } from '../../../main/ets/data/ExpressionSignalChatBridge';
import { ChatRequest } from '../../../main/ets/data/Models';
import { StableExpressionSignal } from '../../../main/ets/service/ExpressionSignalProcessor';

export default function expressionSignalChatBridgeTest(): void {
  describe('ExpressionSignalChatBridge', () => {
    it('omits expression_signal when no stable signal exists', 0, () => {
      const request: ChatRequest = { message: 'hello', session_id: 's', stream: true };
      const mapped = withExpressionSignal(request, undefined);
      expect(mapped.expression_signal).assertUndefined();
    });

    it('maps stable signal fields to the backend snake_case DTO', 0, () => {
      const request: ChatRequest = { message: 'hello', session_id: 's', stream: true };
      const signal: StableExpressionSignal = {
        label: 'happy', confidence: 0.82, isStable: true, timestamp: 123, modelVersion: 'resnet18-int8'
      };
      const mapped = withExpressionSignal(request, signal);
      expect(mapped.expression_signal?.label).assertEqual('happy');
      expect(mapped.expression_signal?.confidence).assertEqual(0.82);
      expect(mapped.expression_signal?.is_stable).assertTrue();
      expect(mapped.expression_signal?.model_version).assertEqual('resnet18-int8');
    });
  });
}
