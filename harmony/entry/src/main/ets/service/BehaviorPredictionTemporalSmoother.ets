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

  reset(): void {
    this.smoothed = [];
  }
}