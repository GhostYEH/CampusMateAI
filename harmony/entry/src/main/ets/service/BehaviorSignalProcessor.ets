import { BehaviorV34Label, BehaviorV34Result } from './BehaviorV34Decision';
import {
  BehaviorDisplayState,
  BehaviorDisplayStates,
  BehaviorDisplayStateKind
} from './LearningContinuityStateMachine';

export enum StableBehaviorEvent {
  PHONE_DISTRACTION = 'PHONE_DISTRACTION',
  STUDENT_ABSENT = 'STUDENT_ABSENT',
  FOCUS_RECOVERED = 'FOCUS_RECOVERED',
  POSSIBLE_DISTRACTION = 'POSSIBLE_DISTRACTION',
  STABLE_LEARNING = 'STABLE_LEARNING'
}

export interface BehaviorSignalConfig {
  phoneUseThresholdMs: number;
  phoneReminderCooldownMs: number;
  noVisibleStudyThresholdMs: number;
  learningRecoveryThresholdMs: number;
  confidenceThreshold: number;
  startupWarmupMs: number;
  stableBehaviorWindowMs: number;
  stableBehaviorDominantRatio: number;
  stableBehaviorAverageConfidence: number;
}

interface BehaviorSample {
  label: BehaviorV34Label;
  confidence: number;
  timestampMs: number;
}

const DEFAULT_CONFIG: BehaviorSignalConfig = {
  phoneUseThresholdMs: 3000,
  phoneReminderCooldownMs: 600000,
  noVisibleStudyThresholdMs: 20000,
  learningRecoveryThresholdMs: 5000,
  confidenceThreshold: 0.5,
  startupWarmupMs: 1500,
  stableBehaviorWindowMs: 2000,
  stableBehaviorDominantRatio: 0.70,
  stableBehaviorAverageConfidence: 0.65
};

/**
 * Converts raw V3.4/TSM predictions into the display state shown by Focus and
 * detects stable behavioral events. Mirrors the Android BehaviorSignalProcessor
 * while respecting the smaller label set of the Harmony model contract.
 */
export class BehaviorSignalProcessor {
  private readonly config: BehaviorSignalConfig;
  private behaviorObservationStartedAt: number = 0;
  private readonly behaviorSamples: BehaviorSample[] = [];
  private phoneSince: number = -1;
  private lastPhoneReminderAt: number = -1;
  private noVisibleStudySince: number = -1;
  private currentlyNoVisibleDistracted: boolean = false;
  private lastNoVisibleRecoveryStart: number = -1;
  private lastAbsentStart: number = 0;
  private currentlyAbsent: boolean = false;
  private lastLearningStart: number = 0;

  constructor(config?: BehaviorSignalConfig) {
    this.config = config ?? DEFAULT_CONFIG;
  }

  beginBehaviorObservation(startedAtMs: number): void {
    this.behaviorObservationStartedAt = startedAtMs;
    this.behaviorSamples.length = 0;
  }

  processDisplayState(result: BehaviorV34Result, timestampMs: number): BehaviorDisplayState {
    if (!result.isStable || result.label === BehaviorV34Label.CONTINUE_OBSERVING) {
      return BehaviorDisplayStates.noStableBehavior();
    }
    if (this.behaviorObservationStartedAt === 0) {
      this.beginBehaviorObservation(timestampMs);
    }
    this.behaviorSamples.push({
      label: result.label,
      confidence: result.confidence,
      timestampMs: timestampMs
    });
    const windowStart: number = timestampMs - this.config.stableBehaviorWindowMs;
    while (this.behaviorSamples.length > 0 && this.behaviorSamples[0].timestampMs < windowStart) {
      this.behaviorSamples.shift();
    }
    if (timestampMs - this.behaviorObservationStartedAt < this.config.startupWarmupMs) {
      return BehaviorDisplayStates.observing();
    }
    if (this.behaviorSamples.length === 0) return BehaviorDisplayStates.noStableBehavior();
    const counts: Map<BehaviorV34Label, number> = new Map();
    const confidences: Map<BehaviorV34Label, number[]> = new Map();
    for (const sample of this.behaviorSamples) {
      counts.set(sample.label, (counts.get(sample.label) ?? 0) + 1);
      const list: number[] = confidences.get(sample.label) ?? [];
      list.push(sample.confidence);
      confidences.set(sample.label, list);
    }
    let dominantLabel: BehaviorV34Label = BehaviorV34Label.CONTINUE_OBSERVING;
    let dominantCount: number = 0;
    counts.forEach((count: number, label: BehaviorV34Label) => {
      if (count > dominantCount) {
        dominantCount = count;
        dominantLabel = label;
      }
    });
    const dominantRatio: number = dominantCount / this.behaviorSamples.length;
    const confList: number[] = confidences.get(dominantLabel) ?? [];
    let averageConfidence: number = 0;
    for (const c of confList) averageConfidence += c;
    averageConfidence /= confList.length;
    if (dominantRatio >= this.config.stableBehaviorDominantRatio &&
      averageConfidence >= this.config.stableBehaviorAverageConfidence) {
      return BehaviorDisplayStates.stable(dominantLabel, averageConfidence);
    }
    return BehaviorDisplayStates.noStableBehavior();
  }

  process(result: BehaviorV34Result, timestampMs: number): StableBehaviorEvent[] {
    const events: StableBehaviorEvent[] = [];
    if (!result.isStable || result.label === BehaviorV34Label.CONTINUE_OBSERVING) return events;
    const now: number = timestampMs;

    if (result.label === BehaviorV34Label.PHONE_INTERACTION) {
      if (this.phoneSince < 0) this.phoneSince = now;
      if (now - this.phoneSince >= this.config.phoneUseThresholdMs &&
        (this.lastPhoneReminderAt < 0 || now - this.lastPhoneReminderAt >= this.config.phoneReminderCooldownMs)) {
        events.push(StableBehaviorEvent.PHONE_DISTRACTION);
        this.lastPhoneReminderAt = now;
      }
    } else {
      this.phoneSince = -1;
    }

    if (result.label === BehaviorV34Label.NO_VISIBLE_STUDY) {
      this.lastNoVisibleRecoveryStart = -1;
      if (this.noVisibleStudySince < 0) this.noVisibleStudySince = now;
      if (!this.currentlyNoVisibleDistracted &&
        now - this.noVisibleStudySince >= this.config.noVisibleStudyThresholdMs) {
        this.currentlyNoVisibleDistracted = true;
        events.push(StableBehaviorEvent.POSSIBLE_DISTRACTION);
      }
    } else if (this.isStudyBehavior(result.label)) {
      this.noVisibleStudySince = -1;
      if (this.currentlyNoVisibleDistracted) {
        if (this.lastNoVisibleRecoveryStart < 0) this.lastNoVisibleRecoveryStart = now;
        if (now - this.lastNoVisibleRecoveryStart >= this.config.learningRecoveryThresholdMs) {
          this.currentlyNoVisibleDistracted = false;
          this.lastNoVisibleRecoveryStart = -1;
          events.push(StableBehaviorEvent.FOCUS_RECOVERED);
        }
      }
    }

    if (this.isStudyBehavior(result.label) && !this.currentlyAbsent) {
      events.push(StableBehaviorEvent.STABLE_LEARNING);
      this.lastLearningStart = now;
    }

    return events;
  }

  reset(): void {
    this.behaviorObservationStartedAt = 0;
    this.behaviorSamples.length = 0;
    this.phoneSince = -1;
    this.lastPhoneReminderAt = -1;
    this.noVisibleStudySince = -1;
    this.currentlyNoVisibleDistracted = false;
    this.lastNoVisibleRecoveryStart = -1;
    this.lastAbsentStart = 0;
    this.currentlyAbsent = false;
    this.lastLearningStart = 0;
  }

  private isStudyBehavior(label: BehaviorV34Label): boolean {
    return label === BehaviorV34Label.READ || label === BehaviorV34Label.WRITE ||
      label === BehaviorV34Label.COMPUTER;
  }
}