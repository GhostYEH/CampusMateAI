export interface ExpressionFrame {
  label: string;
  confidence: number;
  timestamp: number;
}

export interface StableExpressionSignal {
  label: string;
  confidence: number;
  isStable: boolean;
  timestamp: number;
  modelVersion: string;
}

export interface ExpressionThresholds {
  angry?: number;
  disgust?: number;
  fear?: number;
  happy?: number;
  neutral?: number;
  sad?: number;
  surprise?: number;
}

const UNKNOWN_LABEL: string = 'UNKNOWN';
const NO_FACE_LABEL: string = 'NO_FACE';

/** Matches the Android preprocessing.json class thresholds; callers may override for a model. */
export const DEFAULT_EXPRESSION_THRESHOLDS: ExpressionThresholds = {
  angry: 0.81,
  disgust: 0.91,
  fear: 0.80,
  happy: 0.30,
  neutral: 0.83,
  sad: 0.68,
  surprise: 0.78
};

/**
 * Pure in-memory gate shared by future Harmony camera providers.
 * It never receives or stores image data.
 */
export class ExpressionSignalProcessor {
  private readonly classThresholds: ExpressionThresholds;
  private readonly globalThreshold: number;
  private readonly stableFrameCount: number;
  private readonly alpha: number;
  private readonly maxAgeMs: number;
  private readonly modelVersion: string;
  private candidateLabel: string = '';
  private candidateCount: number = 0;
  private smoothedConfidence: number = 0;
  private latestStableSignal?: StableExpressionSignal = undefined;

  constructor(
    classThresholds: ExpressionThresholds = DEFAULT_EXPRESSION_THRESHOLDS,
    globalThreshold: number = 0.7,
    stableFrameCount: number = 3,
    alpha: number = 0.4,
    maxAgeMs: number = 1500,
    modelVersion: string = 'harmony-expression-unknown'
  ) {
    this.classThresholds = classThresholds;
    this.globalThreshold = globalThreshold;
    this.stableFrameCount = Math.max(1, stableFrameCount);
    this.alpha = Math.min(1, Math.max(0, alpha));
    this.maxAgeMs = Math.max(0, maxAgeMs);
    this.modelVersion = modelVersion;
  }

  push(frame: ExpressionFrame): StableExpressionSignal | undefined {
    if (frame.label === NO_FACE_LABEL || frame.label === UNKNOWN_LABEL || !this.accepts(frame)) {
      this.resetCandidate();
      return undefined;
    }

    if (this.candidateLabel === frame.label) {
      this.candidateCount += 1;
      this.smoothedConfidence = this.alpha * frame.confidence + (1 - this.alpha) * this.smoothedConfidence;
    } else {
      this.candidateLabel = frame.label;
      this.candidateCount = 1;
      this.smoothedConfidence = frame.confidence;
    }

    if (this.candidateCount < this.stableFrameCount) return undefined;
    this.latestStableSignal = {
      label: this.candidateLabel,
      confidence: this.smoothedConfidence,
      isStable: true,
      timestamp: frame.timestamp,
      modelVersion: this.modelVersion
    };
    return this.latestStableSignal;
  }

  latest(nowMs: number = Date.now()): StableExpressionSignal | undefined {
    if (this.latestStableSignal === undefined) return undefined;
    if (nowMs - this.latestStableSignal.timestamp > this.maxAgeMs) {
      this.latestStableSignal = undefined;
      return undefined;
    }
    return this.latestStableSignal;
  }

  reset(): void {
    this.resetCandidate();
    this.latestStableSignal = undefined;
  }

  private accepts(frame: ExpressionFrame): boolean {
    const configured = this.thresholdFor(frame.label);
    const threshold = configured === undefined ? this.globalThreshold : configured;
    return Number.isFinite(frame.confidence) && frame.confidence >= threshold;
  }

  private thresholdFor(label: string): number | undefined {
    if (label === 'angry') return this.classThresholds.angry;
    if (label === 'disgust') return this.classThresholds.disgust;
    if (label === 'fear') return this.classThresholds.fear;
    if (label === 'happy') return this.classThresholds.happy;
    if (label === 'neutral') return this.classThresholds.neutral;
    if (label === 'sad') return this.classThresholds.sad;
    if (label === 'surprise') return this.classThresholds.surprise;
    return undefined;
  }

  private resetCandidate(): void {
    this.candidateLabel = '';
    this.candidateCount = 0;
    this.smoothedConfidence = 0;
    this.latestStableSignal = undefined;
  }
}
