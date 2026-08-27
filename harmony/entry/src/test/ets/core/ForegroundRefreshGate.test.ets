import { describe, expect, it } from '@ohos/hypium';
import { ForegroundRefreshGate } from '../../../main/ets/core/ForegroundRefreshGate';

export default function foregroundRefreshGateTest(): void {
  describe('ForegroundRefreshGate', () => {
    it('blocks hidden, concurrent, and too-frequent foreground work', 0, () => {
      const gate = new ForegroundRefreshGate(30_000);

      gate.setVisible(false);
      expect(gate.tryStart(1_000)).assertFalse();

      gate.setVisible(true);
      expect(gate.tryStart(1_000)).assertTrue();
      expect(gate.tryStart(2_000)).assertFalse();

      gate.finish();
      expect(gate.tryStart(20_000)).assertFalse();
      expect(gate.tryStart(31_000)).assertTrue();
    });

    it('allows immediate work after a reset', 0, () => {
      const gate = new ForegroundRefreshGate(30_000);
      expect(gate.tryStart(5_000)).assertTrue();
      gate.finish();
      gate.reset();

      expect(gate.tryStart(5_001)).assertTrue();
    });
  });
}
