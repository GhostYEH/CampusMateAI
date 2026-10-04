import { BehaviorV34Decision, BehaviorV34Label, BehaviorV34Result } from './BehaviorV34Decision';
import { BehaviorHybridPolicy } from './BehaviorHybridPolicy';

/**
 * Applies EMA smoothing to model probabilities before product-level temporal rules.
 * The first prediction is returned unchanged so a focus session can begin observing immediately.
 */
export class BehaviorPredictionTemporalSmoother {
  private readonly alpha: number;
  private smoothed: number[] = [];

  constructor(alpha: number = 0.35) {
    this.alpha = Math.min(1, Math.max(0, alpha));
  }

  smooth(raw: number[]): number[] {
    if (raw.length === 0) {
      this.reset();
      return raw;
    }
    if (this.smoothed.length !== raw.length) {
      this.smoothed = raw.slice();
      return raw.slice();
    }
    const next: number[] = new Array<number>(raw.length);
    for (let i: number = 0; i < raw.length; i++) {
      next[i] = this.smoothed[i] + this.alpha * (raw[i] - this.smoothed[i]);
    }
    this.smoothed = next;
    return next.slice();
  }

  smoothResult(raw: BehaviorV34Result): BehaviorV34Result {
    const probabilities: number[] = this.smooth(raw.probabilities);
    const labels: BehaviorV34Label[] = probabilities.length === 5 ? [
      BehaviorV34Label.READ, BehaviorV34Label.WRITE, BehaviorV34Label.PHONE_INTERACTION,
      BehaviorV34Label.COMPUTER, BehaviorV34Label.NO_VISIBLE_STUDY
    ] : [
      BehaviorV34Label.READ, BehaviorV34Label.WRITE, BehaviorV34Label.PHONE_INTERACTION,
      BehaviorV34Label.NO_VISIBLE_STUDY
    ];
    let bestIndex: number = 0;
    let best: number = 0;
    let second: number = 0;
    for (let index: number = 0; index < probabilities.length; index++) {
      if (probabilities[index] > best) {
        second = best;
        best = probabilities[index];
        bestIndex = index;
      } else {
        second = Math.max(second, probabilities[index]);
      }
    }
    const minimumConfidence: number = probabilities.length === 5 ?
      BehaviorHybridPolicy.MINIMUM_CONFIDENCE : BehaviorV34Decision.MIN_CONFIDENCE;
    const margin: number = best - second;
    // Do not revive rejected labels or bypass the hybrid eligibility checks.
    const accepted: boolean = raw.isStable && raw.label !== BehaviorV34Label.CONTINUE_OBSERVING &&
      raw.label === labels[bestIndex] && best >= minimumConfidence &&
      margin >= BehaviorV34Decision.MIN_MARGIN;
    return {
      label: accepted ? labels[bestIndex] : BehaviorV34Label.CONTINUE_OBSERVING,
      confidence: best,
      margin: margin,
      isStable: accepted,
      probabilities: probabilities
    };
  }

  reset(): void {
    this.smoothed = [];
  }
}
