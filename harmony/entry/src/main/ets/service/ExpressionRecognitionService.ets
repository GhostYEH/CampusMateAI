import { ExpressionRecognitionProvider, UnavailableExpressionProvider } from './ExpressionRecognitionProvider';
import { StableExpressionSignal } from './ExpressionSignalProcessor';

export interface ExpressionRecognitionStats {
  observedSignals: number;
  stableSignals: number;
  unknownSignals: number;
  noFaceSignals: number;
}

/** Coordinates provider lifecycle without exposing image data to the UI or API layer. */
export class ExpressionRecognitionService {
  private readonly provider: ExpressionRecognitionProvider;
  private started: boolean = false;
  private lastObservedTimestamp: number = -1;
  private readonly counters: ExpressionRecognitionStats = {
    observedSignals: 0,
    stableSignals: 0,
    unknownSignals: 0,
    noFaceSignals: 0
  };

  constructor(provider: ExpressionRecognitionProvider = new UnavailableExpressionProvider()) {
    this.provider = provider;
  }

  async start(): Promise<void> {
    if (this.started) return;
    await this.provider.start();
    this.started = true;
  }

  async stop(): Promise<void> {
    if (!this.started) return;
    await this.provider.stop();
    this.started = false;
  }

  available(): boolean {
    return this.provider.available();
  }

  statusDetail(): string {
    return this.provider.detail();
  }

  latestStableSignal(nowMs: number = Date.now()): StableExpressionSignal | undefined {
    if (!this.started) return undefined;
    const signal = this.provider.latestSignal();
    if (signal === undefined || signal.timestamp === this.lastObservedTimestamp) return this.validStable(signal, nowMs);
    this.lastObservedTimestamp = signal.timestamp;
    this.counters.observedSignals += 1;
    if (signal.label === 'NO_FACE') this.counters.noFaceSignals += 1;
    if (signal.label === 'UNKNOWN') this.counters.unknownSignals += 1;
    if (signal.isStable) this.counters.stableSignals += 1;
    return this.validStable(signal, nowMs);
  }

  stats(): ExpressionRecognitionStats {
    return {
      observedSignals: this.counters.observedSignals,
      stableSignals: this.counters.stableSignals,
      unknownSignals: this.counters.unknownSignals,
      noFaceSignals: this.counters.noFaceSignals
    };
  }

  private validStable(signal: StableExpressionSignal | undefined, nowMs: number): StableExpressionSignal | undefined {
    if (signal === undefined || !signal.isStable) return undefined;
    if (nowMs - signal.timestamp < -2000 || nowMs - signal.timestamp > 5000) return undefined;
    if (signal.label === 'UNKNOWN' || signal.label === 'NO_FACE') return undefined;
    return signal;
  }
}
