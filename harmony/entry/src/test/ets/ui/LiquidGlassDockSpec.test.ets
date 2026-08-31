import { describe, expect, it } from '@ohos/hypium';
import { liquidGlassDockStyle } from '../../../main/ets/ui/LiquidGlassDockSpec';

export default function liquidGlassDockSpecTest(): void {
  describe('LiquidGlassDockSpec', () => {
    it('keeps the light dock translucent so the backdrop remains visible', 0, () => {
      const style = liquidGlassDockStyle(false, false);

      expect(style.backdropBlur).assertEqual(32);
      expect(style.surfaceColor).assertEqual('#66FFFFFF');
      expect(style.highlightColor).assertEqual('#99FFFFFF');
      expect(style.motionDuration).assertEqual(260);
      expect(style.pressWaveEnabled).assertTrue();
      expect(style.pressWaveDuration).assertEqual(420);
      expect(style.pressWaveDiameter).assertEqual(76);
    });

    it('uses a darker translucent surface in dark mode', 0, () => {
      const style = liquidGlassDockStyle(true, false);

      expect(style.surfaceColor).assertEqual('#73162236');
      expect(style.selectedSurfaceColor).assertEqual('#526F78FF');
      expect(style.shadowColor).assertEqual('#80000000');
    });

    it('removes glass transition motion when reduced motion is enabled', 0, () => {
      const style = liquidGlassDockStyle(false, true);

      expect(style.motionDuration).assertEqual(0);
      expect(style.pressScale).assertEqual(1.0);
      expect(style.pressWaveEnabled).assertFalse();
      expect(style.pressWaveDuration).assertEqual(0);
    });
  });
}
