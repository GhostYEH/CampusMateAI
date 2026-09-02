import { describe, expect, it } from '@ohos/hypium';
import { liquidGlassSku } from '../../../main/ets/ui/Theme';

export default function liquidGlassSkuTest(): void {
  describe('LiquidGlassSku', () => {
    it('provides translucent blur and highlight tokens for light and dark cards', 0, () => {
      const light = liquidGlassSku(false);
      const dark = liquidGlassSku(true);
      expect(light.backdropBlur).assertEqual(18);
      expect(light.surface).assertEqual('#B8FFFFFF');
      expect(light.border).assertEqual('#99FFFFFF');
      expect(dark.surface).assertEqual('#B8142738');
      expect(dark.border).assertEqual('#559CC7D0');
    });

    it('keeps glass motion disabled when reduced motion is requested', 0, () => {
      expect(liquidGlassSku(false, true).motionDuration).assertEqual(0);
      expect(liquidGlassSku(true, false).motionDuration).assertEqual(260);
    });
  });
}
