import { describe, expect, it } from '@ohos/hypium';
import { ExpressionModelContract } from '../../../main/ets/service/ExpressionModelContract';

export default function expressionModelContractTest(): void {
  describe('ExpressionModelContract', () => {
    it('accepts only the deployed NHWC input tensor', 0, () => {
      expect(ExpressionModelContract.acceptsInput([1, 96, 96, 3], 96 * 96 * 3)).assertTrue();
      expect(ExpressionModelContract.acceptsInput([1, 3, 96, 96], 96 * 96 * 3)).assertFalse();
    });

    it('requires a float32 seven-logit output tensor', 0, () => {
      expect(ExpressionModelContract.acceptsOutput([1, 7], 7, 28)).assertTrue();
      expect(ExpressionModelContract.acceptsOutput([7], 7, 28)).assertFalse();
      expect(ExpressionModelContract.acceptsOutput([1, 7], 7, 14)).assertFalse();
    });
  });
}
