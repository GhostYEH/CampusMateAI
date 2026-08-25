import { describe, expect, it } from '@ohos/hypium';
import { ExpressionSignalProcessor, ExpressionFrame } from '../../../main/ets/service/ExpressionSignalProcessor';

export default function expressionSignalProcessorTest(): void {
  describe('ExpressionSignalProcessor', () => {
    it('rejects a class prediction below its class threshold', 0, () => {
      const processor = new ExpressionSignalProcessor({ happy: 0.8 }, 0.7, 2, 0.5);
      const result = processor.push({ label: 'happy', confidence: 0.79, timestamp: 1 });
      expect(result).assertEqual(undefined);
    });

    it('falls back to the global threshold for an unknown class', 0, () => {
      const processor = new ExpressionSignalProcessor({}, 0.7, 1, 0.5);
      expect(processor.push({ label: 'neutral', confidence: 0.69, timestamp: 1 })).assertEqual(undefined);
      expect(processor.push({ label: 'neutral', confidence: 0.71, timestamp: 2 })?.label).assertEqual('neutral');
    });

    it('requires consecutive frames before returning a stable signal', 0, () => {
      const processor = new ExpressionSignalProcessor({}, 0.3, 2, 0.5);
      expect(processor.push({ label: 'happy', confidence: 0.9, timestamp: 1 })).assertEqual(undefined);
      const stable = processor.push({ label: 'happy', confidence: 0.9, timestamp: 2 });
      expect(stable?.label).assertEqual('happy');
      expect(stable?.isStable).assertTrue();
    });

    it('clears state on NO_FACE and returns no signal', 0, () => {
      const processor = new ExpressionSignalProcessor({}, 0.3, 1, 0.5);
      processor.push({ label: 'happy', confidence: 0.9, timestamp: 1 });
      const noFace: ExpressionFrame = { label: 'NO_FACE', confidence: 0, timestamp: 2 };
      expect(processor.push(noFace)).assertEqual(undefined);
      expect(processor.latest()).assertEqual(undefined);
    });

    it('does not return an expired stable signal', 0, () => {
      const processor = new ExpressionSignalProcessor({}, 0.3, 1, 0.5, 100);
      processor.push({ label: 'happy', confidence: 0.9, timestamp: 1 });
      expect(processor.latest(102)).assertEqual(undefined);
    });
  });
}
