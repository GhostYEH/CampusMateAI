import { describe, expect, it } from '@ohos/hypium';
import {
  BehaviorHybridPolicy,
  BehaviorTsmContract,
  BehaviorTsmResult
} from '../../../main/ets/service/BehaviorHybridPolicy';
import { BehaviorTemporalFrameBuffer } from '../../../main/ets/service/MindSporeBehaviorProvider';
import { BehaviorV34Label, BehaviorV34Result } from '../../../main/ets/service/BehaviorV34Decision';

function singleResult(probabilities: number[]): BehaviorV34Result {
  const ranked: number[] = probabilities
    .map((value: number, index: number) => index)
    .sort((left: number, right: number) => probabilities[right] - probabilities[left]);
  const bestIndex: number = ranked[0];
  const secondIndex: number = ranked[1] ?? ranked[0];
  const labels: BehaviorV34Label[] = [
    BehaviorV34Label.READ,
    BehaviorV34Label.WRITE,
    BehaviorV34Label.PHONE_INTERACTION,
    BehaviorV34Label.NO_VISIBLE_STUDY
  ];
  return {
    label: labels[bestIndex],
    confidence: probabilities[bestIndex],
    margin: probabilities[bestIndex] - probabilities[secondIndex],
    isStable: true,
    probabilities: probabilities
  };
}

function temporalResult(probabilities: number[]): BehaviorTsmResult {
  const ranked: number[] = probabilities
    .map((value: number, index: number) => index)
    .sort((left: number, right: number) => probabilities[right] - probabilities[left]);
  const bestIndex: number = ranked[0];
  const secondIndex: number = ranked[1] ?? ranked[0];
  const labels: BehaviorV34Label[] = [
    BehaviorV34Label.READ,
    BehaviorV34Label.WRITE,
    BehaviorV34Label.PHONE_INTERACTION,
    BehaviorV34Label.COMPUTER,
    BehaviorV34Label.NO_VISIBLE_STUDY
  ];
  return {
    label: labels[bestIndex],
    confidence: probabilities[bestIndex],
    margin: probabilities[bestIndex] - probabilities[secondIndex],
    isStable: true,
    probabilities: probabilities
  };
}

export default function behaviorHybridPolicyTest(): void {
  describe('BehaviorHybridPolicy', () => {
    it('retains exactly the latest eight CHW tensors', 0, () => {
      const buffer = new BehaviorTemporalFrameBuffer();
      for (let index: number = 0; index < 10; index++) {
        const tensor = new Float32Array(3 * 224 * 224);
        tensor[0] = index;
        buffer.push(tensor);
      }
      const snapshot: Float32Array[] = buffer.snapshot();
      expect(snapshot.length).assertEqual(8);
      expect(snapshot[0][0]).assertEqual(2);
      expect(snapshot[7][0]).assertEqual(9);
    });

    it('stacks all eight tensors in insertion order', 0, () => {
      const buffer = new BehaviorTemporalFrameBuffer();
      for (let index: number = 0; index < 8; index++) {
        const tensor = new Float32Array(3 * 224 * 224);
        tensor[0] = index;
        buffer.push(tensor);
      }
      const stacked: Float32Array | undefined = buffer.toModelInput();
      expect(stacked?.length ?? 0).assertEqual(8 * 3 * 224 * 224);
      const frameStride: number = 3 * 224 * 224;
      expect(stacked?.[0] ?? -1).assertEqual(0);
      expect(stacked?.[frameStride] ?? -1).assertEqual(1);
      expect(stacked?.[frameStride * 7] ?? -1).assertEqual(7);
    });

    it('empties the temporal buffer after reset', 0, () => {
      const buffer = new BehaviorTemporalFrameBuffer();
      buffer.push(new Float32Array(3 * 224 * 224));
      buffer.reset();
      expect(buffer.snapshot().length).assertEqual(0);
      expect(buffer.toModelInput()).assertUndefined();
    });

    it('decodes TSM logits in the exported five-class order', 0, () => {
      const decoded = BehaviorTsmContract.decode([0, 0, 0, 10, 0]);
      expect(decoded.label).assertEqual(BehaviorV34Label.COMPUTER);
      expect(Math.abs(decoded.probabilities.reduce((sum: number, value: number) => sum + value, 0) - 1) < 0.0001)
        .assertTrue();
    });

    it('requires at least eight frames and a two-second interval before temporal runs', 0, () => {
      const uncertain = singleResult([0.34, 0.31, 0.20, 0.15]);
      expect(BehaviorHybridPolicy.shouldRunTemporal(uncertain, undefined, 5000, 0, 7)).assertFalse();
      expect(BehaviorHybridPolicy.shouldRunTemporal(uncertain, undefined, 5000, 4000, 16)).assertFalse();
    });

    it('triggers temporal runs after the periodic interval, low confidence, narrow margins, label changes, and phone detections', 0, () => {
      const uncertain = singleResult([0.34, 0.31, 0.20, 0.15]);
      const confidentRead = singleResult([0.85, 0.05, 0.05, 0.05]);
      const phone = singleResult([0.10, 0.05, 0.80, 0.05]);
      expect(BehaviorHybridPolicy.shouldRunTemporal(uncertain, undefined, 5000, 2000, 16)).assertTrue();
      expect(BehaviorHybridPolicy.shouldRunTemporal(confidentRead, BehaviorV34Label.READ, 5000, 2000, 16)).assertTrue();
      expect(BehaviorHybridPolicy.shouldRunTemporal(confidentRead, BehaviorV34Label.WRITE, 4500, 2000, 16)).assertTrue();
      expect(BehaviorHybridPolicy.shouldRunTemporal(phone, BehaviorV34Label.PHONE_INTERACTION, 4500, 2000, 16))
        .assertTrue();
    });

    it('lets temporal phone evidence outweigh a single-frame reading and keeps probabilities normalized', 0, () => {
      const result = BehaviorHybridPolicy.fuse(
        singleResult([0.55, 0.03, 0.40, 0.02]),
        temporalResult([0.05, 0.02, 0.90, 0.01, 0.02]),
        false
      );
      expect(result.label).assertEqual(BehaviorV34Label.PHONE_INTERACTION);
      expect(Math.abs(result.probabilities.reduce((sum: number, value: number) => sum + value, 0) - 1) < 0.0001)
        .assertTrue();
    });

    it('does not allow temporal writing to override a different single-frame top label', 0, () => {
      const result = BehaviorHybridPolicy.fuse(
        singleResult([0.42, 0.40, 0.10, 0.08]),
        temporalResult([0.03, 0.90, 0.02, 0.02, 0.03]),
        false
      );
      expect(result.label === BehaviorV34Label.WRITE).assertFalse();
    });

    it('requires two confirmations before accepting computer output', 0, () => {
      const single = singleResult([0.10, 0.05, 0.05, 0.80]);
      const temporal = temporalResult([0.02, 0.02, 0.02, 0.90, 0.04]);
      expect(BehaviorHybridPolicy.fuse(single, temporal, false).label === BehaviorV34Label.COMPUTER).assertFalse();
      expect(BehaviorHybridPolicy.fuse(single, temporal, true).label).assertEqual(BehaviorV34Label.COMPUTER);
    });
  });
}
