import { describe, expect, it } from '@ohos/hypium';
import { ExpressionModelMath } from '../../../main/ets/service/ExpressionModelMath';
import { ExpressionGreetingPolicy } from '../../../main/ets/service/ExpressionGreetingPolicy';

export default function expressionModelMathTest(): void {
  describe('ExpressionModelMath', () => {
    it('uses grayscale replicated NHWC normalization', 0, () => {
      const output = ExpressionModelMath.rgbaToGrayscaleNhwc(new Uint8Array([255, 0, 0, 255]), 1, 1);
      expect(output?.length).assertEqual(3);
      expect(Math.abs((output?.[0] ?? 0) - (-0.8126)) < 0.01).assertTrue();
    });

    it('decodes logits in the deployed class order', 0, () => {
      const prediction = ExpressionModelMath.decode(new Float32Array([0, 0, 0, 0, 0, 8, 0]));
      expect(prediction?.label).assertEqual('sad');
      expect((prediction?.confidence ?? 0) > 0.99).assertTrue();
    });

    it('uses explicit empathetic but uncertainty-aware wording for sadness', 0, () => {
      const greeting = ExpressionGreetingPolicy.greeting({
        label: 'sad', confidence: 0.8, isStable: true, timestamp: 1, modelVersion: 'v2'
      });
      expect(greeting.indexOf('可能') >= 0).assertTrue();
      expect(greeting.indexOf('别难过') >= 0).assertTrue();
    });
  });
}
