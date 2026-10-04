import { ExpressionModelMath } from './ExpressionModelMath.ts';
import type { ExpressionConfidenceCalibration, ExpressionStateConfidences } from './ExpressionModelMath.ts';

interface StateLogitFrame {
  logits: number[];
  timestamp: number;
}

/** Calibrates the mean of a short same-track raw-logit window; it never averages probabilities. */
export class ExpressionStateConfidenceWindow {
  private readonly frameCount: number;
  private readonly maxAgeMs: number;
  private readonly calibration: ExpressionConfidenceCalibration;
  private frames: StateLogitFrame[] = [];

  constructor(frameCount: number, maxAgeMs: number, calibration: ExpressionConfidenceCalibration) {
    this.frameCount = Math.max(1, Math.floor(frameCount));
    this.maxAgeMs = Math.max(0, maxAgeMs);
    this.calibration = calibration;
  }

  push(logits: number[], timestamp: number): ExpressionStateConfidences | undefined {
    if (logits.length !== 3 || !Number.isFinite(timestamp) ||
      logits.some((value: number) => !Number.isFinite(value))) {
      this.reset();
      return undefined;
    }
    const previous: StateLogitFrame | undefined = this.frames[this.frames.length - 1];
    if (previous !== undefined && (timestamp <= previous.timestamp ||
      timestamp - previous.timestamp > this.maxAgeMs)) this.reset();
    this.frames.push({ logits: logits.slice(), timestamp });
    if (this.frames.length > this.frameCount) this.frames.shift();
    return this.latest(timestamp);
  }

  latest(nowMs: number): ExpressionStateConfidences | undefined {
    if (this.frames.length === 0) return undefined;
    const first: StateLogitFrame = this.frames[0];
    const last: StateLogitFrame = this.frames[this.frames.length - 1];
    if (nowMs < last.timestamp || nowMs - first.timestamp > this.maxAgeMs) {
      this.reset();
      return undefined;
    }
    if (this.frames.length !== this.frameCount) return undefined;
    const means: number[] = [0, 0, 0];
    for (let frameIndex: number = 0; frameIndex < this.frames.length; frameIndex++) {
      for (let stateIndex: number = 0; stateIndex < 3; stateIndex++) {
        means[stateIndex] += this.frames[frameIndex].logits[stateIndex] / this.frameCount;
      }
    }
    return ExpressionModelMath.calibrateStates(means, this.calibration);
  }

  sampleCount(): number { return this.frames.length; }

  reset(): void {
    this.frames = [];
  }
}
