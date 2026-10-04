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

    it('writes grayscale replicated RGB planes in MindSpore NCHW order', 0, () => {
      const pixels = new Uint8Array([255, 0, 0, 255, 0, 255, 0, 255]);
      const nhwc = ExpressionModelMath.rgbaToGrayscaleNhwc(pixels, 2, 1);
      const nchw = ExpressionModelMath.rgbaToGrayscaleNchw(pixels, 2, 1);
      expect(nchw?.length).assertEqual(6);
      expect(Math.abs((nchw?.[0] ?? 0) - (nhwc?.[0] ?? 1)) < 0.000001).assertTrue();
      expect(Math.abs((nchw?.[1] ?? 0) - (nhwc?.[3] ?? 1)) < 0.000001).assertTrue();
      expect(Math.abs((nchw?.[2] ?? 0) - (nhwc?.[1] ?? 1)) < 0.000001).assertTrue();
      expect(Math.abs((nchw?.[3] ?? 0) - (nhwc?.[4] ?? 1)) < 0.000001).assertTrue();
      expect(Math.abs((nchw?.[4] ?? 0) - (nhwc?.[2] ?? 1)) < 0.000001).assertTrue();
      expect(Math.abs((nchw?.[5] ?? 0) - (nhwc?.[5] ?? 1)) < 0.000001).assertTrue();
    });

    it('decodes logits in the deployed class order', 0, () => {
      const prediction = ExpressionModelMath.decode(new Float32Array([0, 0, 0, 0, 0, 8, 0]));
      expect(prediction?.label).assertEqual('sad');
      expect((prediction?.confidence ?? 0) > 0.99).assertTrue();
    });

    it('applies the calibrated expression temperature and independent state maps', 0, () => {
      const prediction = ExpressionModelMath.decode(new Float32Array([0, 0, 0, 0, 0, 4, 0]), 2);
      expect(prediction?.label).assertEqual('sad');
      expect((prediction?.confidence ?? 0) < 0.8).assertTrue();
      const states = ExpressionModelMath.calibrateStates([0, 2, 1], {
        expression_temperature: 2, state_scales: [1, 0.5, 2], state_biases: [0, 1, -1]
      });
      expect(Math.abs((states?.boredom ?? 0) - 0.5) < 0.000001).assertTrue();
      expect(Math.abs((states?.confusion ?? 0) - (1 / (1 + Math.exp(-2)))) < 0.000001).assertTrue();
      expect(Math.abs((states?.frustration ?? 0) - 0.5) < 0.000001).assertTrue();
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
