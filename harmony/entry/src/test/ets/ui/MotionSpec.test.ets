import { describe, expect, it } from '@ohos/hypium';
import { MotionDuration, MotionSpec } from '../../../main/ets/ui/MotionSpec';

export default function motionSpecTest(): void {
  describe('MotionSpec', () => {
    it('keeps the balanced motion rhythm when motion is enabled', 0, () => {
      expect(MotionSpec.duration(false, MotionDuration.PRESS)).assertEqual(150);
      expect(MotionSpec.duration(false, MotionDuration.STATE)).assertEqual(220);
      expect(MotionSpec.duration(false, MotionDuration.PAGE)).assertEqual(300);
      expect(MotionSpec.distance(false, 24)).assertEqual(24);
      expect(MotionSpec.scale(false, 0.96)).assertEqual(0.96);
      expect(MotionSpec.stagger(false, 3)).assertEqual(105);
      expect(MotionSpec.stagger(false, 8)).assertEqual(105);
    });

    it('removes spatial motion and delays when reduced motion is enabled', 0, () => {
      expect(MotionSpec.duration(true, MotionDuration.PAGE)).assertEqual(0);
      expect(MotionSpec.fadeDuration(true, MotionDuration.PAGE)).assertEqual(80);
      expect(MotionSpec.distance(true, 24)).assertEqual(0);
      expect(MotionSpec.scale(true, 0.96)).assertEqual(1);
      expect(MotionSpec.stagger(true, 3)).assertEqual(0);
    });

    it('does not generate negative stagger delays', 0, () => {
      expect(MotionSpec.stagger(false, -2)).assertEqual(0);
    });

    it('gives the navigation glow a breathing range without motion reduction', 0, () => {
      expect(MotionSpec.glowOpacity(false, 0)).assertEqual(0.56);
      expect(MotionSpec.glowOpacity(false, 1)).assertEqual(0.86);
      expect(MotionSpec.glowBlur(false)).assertEqual(12);
    });

    it('keeps the navigation glow static when motion is reduced', 0, () => {
      expect(MotionSpec.glowOpacity(true, 0)).assertEqual(0.62);
      expect(MotionSpec.glowOpacity(true, 1)).assertEqual(0.62);
      expect(MotionSpec.glowBlur(true)).assertEqual(0);
    });
  });
}
