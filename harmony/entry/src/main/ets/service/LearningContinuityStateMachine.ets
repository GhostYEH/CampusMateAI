import { BehaviorV34Label } from './BehaviorV34Decision';

export enum LearningContinuityState {
  OBSERVING = 'OBSERVING',
  STUDYING = 'STUDYING',
  THINKING_OR_ADJUSTING = 'THINKING_OR_ADJUSTING',
  PAUSED = 'PAUSED'
}

export interface LearningContinuityConfig {
  gracePeriodMs: number;
  thinkingWindowEndMs: number;
  pausedAfterMs: number;
}

export interface LearningContinuityResult {
  state: LearningContinuityState;
  continuousStudyStartedAtMs: number | undefined;
}

export enum BehaviorDisplayStateKind {
  OBSERVING = 'OBSERVING',
  NO_STABLE_BEHAVIOR = 'NO_STABLE_BEHAVIOR',
  STABLE = 'STABLE'
}

export interface BehaviorDisplayState {
  kind: BehaviorDisplayStateKind;
  behavior: BehaviorV34Label;
  confidence: number;
}

export class BehaviorDisplayStates {
  static observing(): BehaviorDisplayState {
    return { kind: BehaviorDisplayStateKind.OBSERVING, behavior: BehaviorV34Label.CONTINUE_OBSERVING, confidence: 0 };
  }

  static noStableBehavior(): BehaviorDisplayState {
    return { kind: BehaviorDisplayStateKind.NO_STABLE_BEHAVIOR, behavior: BehaviorV34Label.CONTINUE_OBSERVING, confidence: 0 };
  }

  static stable(behavior: BehaviorV34Label, confidence: number): BehaviorDisplayState {
    return { kind: BehaviorDisplayStateKind.STABLE, behavior: behavior, confidence: confidence };
  }
}

export class LearningContinuityStateMachine {
  private readonly config: LearningContinuityConfig;
  private state: LearningContinuityState = LearningContinuityState.OBSERVING;
  private idleStartedAtMs: number | undefined = undefined;
  private continuousStudyStartedAtMs: number | undefined = undefined;

  constructor(config?: LearningContinuityConfig) {
    this.config = config ?? { gracePeriodMs: 8000, thinkingWindowEndMs: 20000, pausedAfterMs: 20000 };
  }

  reset(): void {
    this.state = LearningContinuityState.OBSERVING;
    this.idleStartedAtMs = undefined;
    this.continuousStudyStartedAtMs = undefined;
  }

  process(displayState: BehaviorDisplayState, timestampMs: number): LearningContinuityResult {
    if (displayState.kind === BehaviorDisplayStateKind.STABLE) {
      if (this.isStudyBehavior(displayState.behavior)) {
        if (this.state === LearningContinuityState.OBSERVING || this.state === LearningContinuityState.PAUSED) {
          this.continuousStudyStartedAtMs = timestampMs;
        }
        this.state = LearningContinuityState.STUDYING;
        this.idleStartedAtMs = undefined;
      } else if (displayState.behavior === BehaviorV34Label.NO_VISIBLE_STUDY) {
        this.handleIdle(timestampMs);
      }
    }
    return { state: this.state, continuousStudyStartedAtMs: this.continuousStudyStartedAtMs };
  }

  private handleIdle(timestampMs: number): void {
    if (this.state === LearningContinuityState.STUDYING ||
      this.state === LearningContinuityState.THINKING_OR_ADJUSTING) {
      if (this.idleStartedAtMs === undefined) this.idleStartedAtMs = timestampMs;
      const idleDuration: number = Math.max(0, timestampMs - this.idleStartedAtMs);
      if (idleDuration < this.config.gracePeriodMs) {
        this.state = LearningContinuityState.STUDYING;
      } else if (idleDuration < this.config.thinkingWindowEndMs) {
        this.state = LearningContinuityState.THINKING_OR_ADJUSTING;
      } else if (idleDuration >= this.config.pausedAfterMs) {
        this.state = LearningContinuityState.PAUSED;
      } else {
        this.state = LearningContinuityState.THINKING_OR_ADJUSTING;
      }
      if (this.state === LearningContinuityState.PAUSED) this.continuousStudyStartedAtMs = undefined;
    } else if (this.state === LearningContinuityState.OBSERVING || this.state === LearningContinuityState.PAUSED) {
      this.state = LearningContinuityState.PAUSED;
      this.idleStartedAtMs = timestampMs;
      this.continuousStudyStartedAtMs = undefined;
    }
  }

  private isStudyBehavior(label: BehaviorV34Label): boolean {
    return label === BehaviorV34Label.READ || label === BehaviorV34Label.WRITE ||
      label === BehaviorV34Label.COMPUTER;
  }
}