import { describe, expect, it } from '@ohos/hypium';
import { ExpressionFaceQuality } from '../../../main/ets/service/ExpressionFaceQuality';

export default function expressionFaceQualityTest(): void {
  describe('ExpressionFaceQuality', () => {
    it('rejects bystanders and a face that is too small', 0, () => {
      expect(ExpressionFaceQuality.evaluate({
        faceCount: 2, faceRatio: 0.3, sharpness: 50, brightness: 120
      }).reason).assertEqual('MULTIPLE_FACES');
      expect(ExpressionFaceQuality.evaluate({
        faceCount: 1, faceRatio: 0.08, sharpness: 50, brightness: 120
      }).reason).assertEqual('TOO_SMALL');
    });

    it('rejects blur and unsafe exposure', 0, () => {
      expect(ExpressionFaceQuality.evaluate({
        faceCount: 1, faceRatio: 0.3, sharpness: 10, brightness: 120
      }).reason).assertEqual('BLUR');
      expect(ExpressionFaceQuality.evaluate({
        faceCount: 1, faceRatio: 0.3, sharpness: 50, brightness: 20
      }).reason).assertEqual('LOW_LIGHT');
    });

    it('accepts one clear and well-lit face', 0, () => {
      const result = ExpressionFaceQuality.evaluate({
        faceCount: 1, faceRatio: 0.3, sharpness: 50, brightness: 120
      });
      expect(result.accepted).assertTrue();
      expect(result.reason).assertEqual('ACCEPTED');
    });
  });
}
