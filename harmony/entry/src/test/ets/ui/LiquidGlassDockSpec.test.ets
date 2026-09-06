import { describe, expect, it } from '@ohos/hypium';
import { clampDockDragOffset, dockDragTargetIndex } from '../../../main/ets/ui/LiquidGlassDockDrag';
import { liquidGlassDockStyle } from '../../../main/ets/ui/LiquidGlassDockSpec';

export default function liquidGlassDockSpecTest(): void {
  describe('LiquidGlassDockSpec', () => {
    it('keeps the light dock translucent so the backdrop remains visible', 0, () => {
      const style = liquidGlassDockStyle(false, false);

      expect(style.backdropBlur).assertEqual(32);
      expect(style.surfaceColor).assertEqual('#66FFFFFF');
      expect(style.highlightColor).assertEqual('#99FFFFFF');
      expect(style.motionDuration).assertEqual(260);
      expect(style.clickGlowEnabled).assertTrue();
      expect(style.clickGlowDuration).assertEqual(300);
      expect(style.clickGlowDiameter).assertEqual(52);
      expect(style.clickGlowColor).assertEqual('#B85B68F2');
      expect(style.chromaticEdgeOpacity).assertEqual(0.16);
      expect(style.maxWidth).assertEqual(560);
    });

    it('uses a darker translucent surface in dark mode', 0, () => {
      const style = liquidGlassDockStyle(true, false);

      expect(style.surfaceColor).assertEqual('#73162236');
      expect(style.selectedSurfaceColor).assertEqual('#526F78FF');
      expect(style.shadowColor).assertEqual('#80000000');
      expect(style.chromaticEdgeOpacity).assertEqual(0.22);
    });

    it('removes glass transition motion when reduced motion is enabled', 0, () => {
      const style = liquidGlassDockStyle(false, true);

      expect(style.motionDuration).assertEqual(0);
      expect(style.clickGlowEnabled).assertFalse();
      expect(style.clickGlowDuration).assertEqual(0);
      expect(style.chromaticEdgeOpacity).assertEqual(0.16);
    });

    it('clamps the draggable selection lens to the dock bounds', 0, () => {
      expect(clampDockDragOffset(2, 5, 100, -500)).assertEqual(-200);
      expect(clampDockDragOffset(2, 5, 100, 500)).assertEqual(200);
      expect(clampDockDragOffset(2, 0, 100, 80)).assertEqual(0);
    });

    it('snaps the selection lens to the nearest item on release', 0, () => {
      expect(dockDragTargetIndex(2, 49, 100, 5)).assertEqual(2);
      expect(dockDragTargetIndex(2, 51, 100, 5)).assertEqual(3);
      expect(dockDragTargetIndex(2, -500, 100, 5)).assertEqual(0);
      expect(dockDragTargetIndex(2, 500, 100, 5)).assertEqual(4);
      expect(dockDragTargetIndex(2, 80, 0, 5)).assertEqual(2);
    });
  });
}
