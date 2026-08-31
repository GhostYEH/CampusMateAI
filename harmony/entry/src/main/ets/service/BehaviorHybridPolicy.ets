import { BehaviorV34Label, BehaviorV34Result } from './BehaviorV34Decision';

export interface BehaviorTsmResult {
  label: BehaviorV34Label;
  confidence: number;
  margin: number;
  isStable: boolean;
  probabilities: number[];
}

export interface BehaviorHybridDecision {
  label: BehaviorV34Label;
  confidence: number;
  margin: number;
  isStable: boolean;
  probabilities: number[];
}

export class BehaviorTsmContract {
  static readonly MODEL_STATE: string = 'READY_BEHAVIOR_TSM_V4';
  static readonly INPUT_FRAME_COUNT: number = 8;
  private static readonly LABELS: BehaviorV34Label[] = [
    BehaviorV34Label.READ,
    BehaviorV34Label.WRITE,
    BehaviorV34Label.PHONE_INTERACTION,
    BehaviorV34Label.COMPUTER,
    BehaviorV34Label.NO_VISIBLE_STUDY
  ];

  static decode(logits: number[]): BehaviorTsmResult {
    if (logits.length !== BehaviorTsmContract.LABELS.length) return BehaviorTsmContract.rejected();
    let maximum: number = -Number.MAX_VALUE;
    for (let index: number = 0; index < logits.length; index++) {
      if (!Number.isFinite(logits[index])) return BehaviorTsmContract.rejected();
      maximum = Math.max(maximum, logits[index]);
    }
    const probabilities: number[] = [];
    let sum: number = 0;
    for (let index: number = 0; index < logits.length; index++) {
      const value: number = Math.exp(logits[index] - maximum);
      probabilities.push(value);
      sum += value;
    }
    if (!Number.isFinite(sum) || sum <= 0) return BehaviorTsmContract.rejected();
    let bestIndex: number = 0;
    let best: number = -1;
    let second: number = -1;
    for (let index: number = 0; index < probabilities.length; index++) {
      probabilities[index] = probabilities[index] / sum;
      if (probabilities[index] > best) {
        second = best;
        best = probabilities[index];
        bestIndex = index;
      } else if (probabilities[index] > second) {
        second = probabilities[index];
      }
    }
    return {
      label: BehaviorTsmContract.LABELS[bestIndex],
      confidence: best,
      margin: best - second,
      isStable: true,
      probabilities: probabilities.slice()
    };
  }

  private static rejected(): BehaviorTsmResult {
    return {
      label: BehaviorV34Label.CONTINUE_OBSERVING,
      confidence: 0,
      margin: 0,
      isStable: false,
      probabilities: []
    };
  }
}

export class BehaviorHybridPolicy {
  static readonly MODEL_STATE: string = 'READY_BEHAVIOR_HYBRID_V4';
  private static readonly MIN_TEMPORAL_INTERVAL_MS: number = 2000;
  private static readonly PERIODIC_TEMPORAL_INTERVAL_MS: number = 3000;
  private static readonly LOW_CONFIDENCE: number = 0.45;
  private static readonly NARROW_MARGIN: number = 0.10;
  private static readonly MINIMUM_CONFIDENCE: number = 0.35;
  private static readonly MINIMUM_MARGIN: number = 0.05;
  private static readonly SINGLE_LABELS: BehaviorV34Label[] = [
    BehaviorV34Label.READ,
    BehaviorV34Label.WRITE,
    BehaviorV34Label.PHONE_INTERACTION,
    BehaviorV34Label.NO_VISIBLE_STUDY
  ];
  private static readonly FUSED_LABELS: BehaviorV34Label[] = [
    BehaviorV34Label.READ,
    BehaviorV34Label.WRITE,
    BehaviorV34Label.PHONE_INTERACTION,
    BehaviorV34Label.COMPUTER,
    BehaviorV34Label.NO_VISIBLE_STUDY
  ];

  static shouldRunTemporal(
    single: BehaviorV34Result,
    previousSingleTop: BehaviorV34Label | undefined,
    nowMs: number,
    lastTemporalAtMs: number,
    bufferedFrameCount: number
  ): boolean {
    if (bufferedFrameCount < BehaviorTsmContract.INPUT_FRAME_COUNT) return false;
    const elapsed: number = nowMs - lastTemporalAtMs;
    if (elapsed < BehaviorHybridPolicy.MIN_TEMPORAL_INTERVAL_MS) return false;
    const ranked = BehaviorHybridPolicy.rankSingle(single.probabilities);
    if (ranked === undefined) return false;
    const changed: boolean = previousSingleTop !== undefined && previousSingleTop !== ranked.label;
    return elapsed >= BehaviorHybridPolicy.PERIODIC_TEMPORAL_INTERVAL_MS ||
      ranked.confidence < BehaviorHybridPolicy.LOW_CONFIDENCE ||
      ranked.margin < BehaviorHybridPolicy.NARROW_MARGIN ||
      changed ||
      ranked.label === BehaviorV34Label.PHONE_INTERACTION;
  }

  static fuse(
    single: BehaviorV34Result,
    temporal: BehaviorTsmResult,
    computerConfirmed: boolean
  ): BehaviorHybridDecision {
    const raw: number[] = [
      BehaviorHybridPolicy.weighted(single, temporal, BehaviorV34Label.READ, 0.65, 0.35),
      BehaviorHybridPolicy.weighted(single, temporal, BehaviorV34Label.WRITE, 0.90, 0.10),
      BehaviorHybridPolicy.weighted(single, temporal, BehaviorV34Label.PHONE_INTERACTION, 0.45, 0.55),
      computerConfirmed ? BehaviorHybridPolicy.temporalValue(temporal, BehaviorV34Label.COMPUTER) : 0,
      BehaviorHybridPolicy.weighted(single, temporal, BehaviorV34Label.NO_VISIBLE_STUDY, 0.55, 0.45)
    ];
    let total: number = 0;
    for (let index: number = 0; index < raw.length; index++) total += raw[index];
    const probabilities: number[] = total > 0 ? raw.map((value: number) => value / total) : raw.slice();
    const singleTop: BehaviorV34Label | undefined = BehaviorHybridPolicy.rankSingle(single.probabilities)?.label;
    const ranked: BehaviorHybridDecision[] = [];
    for (let index: number = 0; index < probabilities.length; index++) {
      const label: BehaviorV34Label = BehaviorHybridPolicy.FUSED_LABELS[index];
      if (label === BehaviorV34Label.WRITE && singleTop !== BehaviorV34Label.WRITE) continue;
      ranked.push({
        label: label,
        confidence: probabilities[index],
        margin: 0,
        isStable: true,
        probabilities: probabilities.slice()
      });
    }
    ranked.sort((left: BehaviorHybridDecision, right: BehaviorHybridDecision) => right.confidence - left.confidence);
    const top: BehaviorHybridDecision | undefined = ranked[0];
    const second: number = ranked[1]?.confidence ?? 0;
    const confidence: number = top?.confidence ?? 0;
    const margin: number = confidence - second;
    const accepted: boolean = top !== undefined &&
      confidence >= BehaviorHybridPolicy.MINIMUM_CONFIDENCE &&
      margin >= BehaviorHybridPolicy.MINIMUM_MARGIN;
    return {
      label: accepted && top !== undefined ? top.label : BehaviorV34Label.CONTINUE_OBSERVING,
      confidence: confidence,
      margin: margin,
      isStable: accepted,
      probabilities: probabilities.slice()
    };
  }

  private static rankSingle(probabilities: number[]): BehaviorTsmResult | undefined {
    if (probabilities.length !== BehaviorHybridPolicy.SINGLE_LABELS.length) return undefined;
    let bestIndex: number = 0;
    let best: number = -1;
    let second: number = -1;
    for (let index: number = 0; index < probabilities.length; index++) {
      if (!Number.isFinite(probabilities[index])) return undefined;
      if (probabilities[index] > best) {
        second = best;
        best = probabilities[index];
        bestIndex = index;
      } else if (probabilities[index] > second) {
        second = probabilities[index];
      }
    }
    return {
      label: BehaviorHybridPolicy.SINGLE_LABELS[bestIndex],
      confidence: best,
      margin: best - second,
      isStable: true,
      probabilities: probabilities.slice()
    };
  }

  private static weighted(
    single: BehaviorV34Result,
    temporal: BehaviorTsmResult,
    label: BehaviorV34Label,
    singleWeight: number,
    temporalWeight: number
  ): number {
    return BehaviorHybridPolicy.singleValue(single, label) * singleWeight +
      BehaviorHybridPolicy.temporalValue(temporal, label) * temporalWeight;
  }

  private static singleValue(single: BehaviorV34Result, label: BehaviorV34Label): number {
    const index: number = BehaviorHybridPolicy.SINGLE_LABELS.indexOf(label);
    if (index < 0 || index >= single.probabilities.length) return 0;
    const value: number = single.probabilities[index];
    return Number.isFinite(value) ? value : 0;
  }

  private static temporalValue(temporal: BehaviorTsmResult, label: BehaviorV34Label): number {
    const index: number = BehaviorHybridPolicy.FUSED_LABELS.indexOf(label);
    if (index < 0 || index >= temporal.probabilities.length) return 0;
    const value: number = temporal.probabilities[index];
    return Number.isFinite(value) ? value : 0;
  }
}
