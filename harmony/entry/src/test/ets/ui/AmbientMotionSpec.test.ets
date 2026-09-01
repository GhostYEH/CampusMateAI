import { describe, expect, it } from '@ohos/hypium';
import { MotionSpec } from '../../../main/ets/ui/MotionSpec';

export default function ambientMotionSpecTest(): void {
  describe('AmbientMotionSpec', () => {
    it('keeps ambient detail subtle when motion is enabled', 0, () => {
      expect(MotionSpec.ambientOpacity(false)).assertEqual(0.18);
      expect(MotionSpec.parallaxAmplitude(false, 6)).assertEqual(6);
      expect(MotionSpec.enterTilt(false, -2.5)).assertEqual(-2.5);
    });

    it('removes ambient movement when reduced motion is enabled', 0, () => {
      expect(MotionSpec.ambientOpacity(true)).assertEqual(0);
      expect(MotionSpec.parallaxAmplitude(true, 6)).assertEqual(0);
      expect(MotionSpec.enterTilt(true, -2.5)).assertEqual(0);
    });
  });
}
