import { ExpressionRecognitionProvider, UnavailableExpressionProvider } from './ExpressionRecognitionProvider';
import { StableExpressionSignal } from './ExpressionSignalProcessor';

export interface ExpressionRecognitionStats {
  observedSignals: number;
  stableSignals: number;
  unknownSignals: number;
  noFaceSignals: number;
}

export class ExpressionCameraActivationPolicy {
  static shouldRun(consented: boolean, signedIn: boolean, visible: boolean, activeTab: number): boolean {
    return consented && signedIn && visible && activeTab === 3;
  }
}

/** Coordinates provider lifecycle without exposing image data to the UI or API layer. */
export class ExpressionRecognitionService {
  private readonly provider: ExpressionRecognitionProvider;
  private started: boolean = false;
  private generation: number = 0;
  private desired: boolean = false;
  private startTask: Promise<void> | undefined = undefined;
  private stopTask: Promise<void> | undefined = undefined;
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
    const stopping: Promise<void> | undefined = this.stopTask;
    if (stopping !== undefined) await stopping;
    const existing: Promise<void> | undefined = this.startTask;
    if (existing !== undefined) {
      await existing;
      return;
    }
    this.desired = true;
    this.generation += 1;
    const current: number = this.generation;
    const task: Promise<void> = this.startInternal(current);
    this.startTask = task;
    try {
      await task;
    } finally {
      if (this.startTask === task) this.startTask = undefined;
    }
  }

  async stop(): Promise<void> {
    if (!this.started && this.startTask === undefined && this.stopTask === undefined) return;
    this.desired = false;
    this.generation += 1;
    this.started = false;
    const existing: Promise<void> | undefined = this.stopTask;
    if (existing !== undefined) {
      await existing;
      return;
    }
    const task: Promise<void> = this.stopInternal();
    this.stopTask = task;
    try {
      await task;
    } finally {
      if (this.stopTask === task) this.stopTask = undefined;
    }
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

  private async startInternal(generation: number): Promise<void> {
    await this.provider.start();
    if (!this.desired || generation !== this.generation) return;
    this.started = true;
  }

  private async stopInternal(): Promise<void> {
    const starting: Promise<void> | undefined = this.startTask;
    if (starting !== undefined) await starting.catch(() => {});
    await this.provider.stop();
  }

  private validStable(signal: StableExpressionSignal | undefined, nowMs: number): StableExpressionSignal | undefined {
    if (signal === undefined || !signal.isStable) return undefined;
    if (nowMs - signal.timestamp < -2000 || nowMs - signal.timestamp > 5000) return undefined;
    if (signal.label === 'UNKNOWN' || signal.label === 'NO_FACE') return undefined;
    return signal;
  }
}
