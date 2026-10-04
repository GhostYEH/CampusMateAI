import { describe, expect, it } from '@ohos/hypium';
import { ExpressionModelContract } from '../../../main/ets/service/ExpressionModelContract';

export default function expressionModelContractTest(): void {
  describe('ExpressionModelContract', () => {
    it('requires NCHW for the multitask model and only accepts legacy NHWC when declared', 0, () => {
      expect(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3)).assertTrue();
      expect(ExpressionModelContract.acceptsInput([1, 96, 96, 3], 96 * 96 * 3)).assertFalse();
      expect(ExpressionModelContract.acceptsInput([1, 96, 96, 3], 96 * 96 * 3, 'NHWC')).assertTrue();
      expect(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3, 'NHWC')).assertFalse();
      expect(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3, 'bad')).assertFalse();
    });

    it('requires the ten-logit deployed tensor and accepts explicit legacy seven-output metadata', 0, () => {
      expect(ExpressionModelContract.acceptsOutput([1, 10], 10, 40)).assertTrue();
      expect(ExpressionModelContract.acceptsOutput([10], 10, 40)).assertFalse();
      expect(ExpressionModelContract.acceptsOutput([1, 10], 10, 20)).assertFalse();
      expect(ExpressionModelContract.acceptsOutput([1, 7], 7, 28, 7)).assertTrue();
      expect(ExpressionModelContract.acceptsOutput([1, 7], 7, 28)).assertFalse();
    });
  });
}
