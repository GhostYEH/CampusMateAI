export enum BehaviorV34Label {
  READ = 'READ',
  WRITE = 'WRITE',
  PHONE_INTERACTION = 'PHONE_INTERACTION',
  COMPUTER = 'COMPUTER',
  NO_VISIBLE_STUDY = 'NO_VISIBLE_STUDY',
  CONTINUE_OBSERVING = 'CONTINUE_OBSERVING'
}

export interface BehaviorV34Result {
  label: BehaviorV34Label;
  confidence: number;
  margin: number;
  isStable: boolean;
  probabilities: number[];
}

export interface BehaviorSessionSummary {
  observed_seconds: number;
  study_seconds: number;
  paused_seconds: number;
  longest_continuous_study_seconds: number;
  meaningful_switch_count: number;
  phone_interaction_count: number;
  possible_distraction_count: number;
  absent_count: number;
  reminder_count: number;
  model_version: string;
}

/** Aggregates stable labels only; no frame or per-frame result leaves memory. */
export class BehaviorSessionSummaryTracker {
  private startedAt: number = 0;
  private lastTimestamp: number = 0;
  private lastLabel: BehaviorV34Label | undefined = undefined;
  private studyMs: number = 0;
  private pausedMs: number = 0;
  private currentStudyMs: number = 0;
  private longestStudyMs: number = 0;
  private switchCount: number = 0;
  private phoneCount: number = 0;
  private distractionCount: number = 0;
  private absentCount: number = 0;
  private reminderCount: number = 0;
  private reminderActive: boolean = false;

  reset(startedAt: number = Date.now()): void {
    this.startedAt = startedAt;
    this.lastTimestamp = startedAt;
    this.lastLabel = undefined;
    this.studyMs = 0;
    this.pausedMs = 0;
    this.currentStudyMs = 0;
    this.longestStudyMs = 0;
    this.switchCount = 0;
    this.phoneCount = 0;
    this.distractionCount = 0;
    this.absentCount = 0;
    this.reminderCount = 0;
    this.reminderActive = false;
  }

  process(result: BehaviorV34Result, timestamp: number, reminder: string): void {
    if (!result.isStable || result.label === BehaviorV34Label.CONTINUE_OBSERVING) return;
    this.accumulateUntil(timestamp);
    if (this.lastLabel !== undefined && this.lastLabel !== result.label) this.switchCount += 1;
    if (result.label === BehaviorV34Label.PHONE_INTERACTION &&
      this.lastLabel !== BehaviorV34Label.PHONE_INTERACTION) this.phoneCount += 1;
    if (result.label === BehaviorV34Label.NO_VISIBLE_STUDY &&
      this.lastLabel !== BehaviorV34Label.NO_VISIBLE_STUDY) this.distractionCount += 1;
    const hasReminder: boolean = reminder.length > 0;
    if (hasReminder && !this.reminderActive) this.reminderCount += 1;
    this.reminderActive = hasReminder;
    this.lastLabel = result.label;
  }

  recordAbsence(): void {
    this.absentCount += 1;
  }

  suspend(timestamp: number): void {
    this.accumulateUntil(timestamp);
    this.lastLabel = undefined;
    this.currentStudyMs = 0;
    this.reminderActive = false;
  }

  resume(timestamp: number): void {
    this.lastTimestamp = timestamp;
    this.lastLabel = undefined;
    this.currentStudyMs = 0;
    this.reminderActive = false;
  }

  summary(now: number, modelVersion: string): BehaviorSessionSummary {
    this.accumulateUntil(now);
    return {
      observed_seconds: Math.max(0, Math.floor((now - this.startedAt) / 1000)),
      study_seconds: Math.floor(this.studyMs / 1000),
      paused_seconds: Math.floor(this.pausedMs / 1000),
      longest_continuous_study_seconds: Math.floor(this.longestStudyMs / 1000),
      meaningful_switch_count: this.switchCount,
      phone_interaction_count: this.phoneCount,
      possible_distraction_count: this.distractionCount,
      absent_count: this.absentCount,
      reminder_count: this.reminderCount,
      model_version: modelVersion
    };
  }

  private accumulateUntil(timestamp: number): void {
    const delta: number = Math.max(0, Math.min(2000, timestamp - this.lastTimestamp));
    if (this.isStudy(this.lastLabel)) {
      this.studyMs += delta;
      this.currentStudyMs += delta;
      this.longestStudyMs = Math.max(this.longestStudyMs, this.currentStudyMs);
    } else {
      this.currentStudyMs = 0;
      if (this.lastLabel === BehaviorV34Label.NO_VISIBLE_STUDY) this.pausedMs += delta;
    }
    this.lastTimestamp = timestamp;
  }

  private isStudy(label: BehaviorV34Label | undefined): boolean {
    return label === BehaviorV34Label.READ || label === BehaviorV34Label.WRITE ||
      label === BehaviorV34Label.COMPUTER;
  }
}

export class BehaviorV34Decision {
  static readonly TEMPERATURE: number = 4.841172366232762;
  static readonly MIN_CONFIDENCE: number = 0.30;
  static readonly MIN_MARGIN: number = 0.05;
  private static readonly LABELS: BehaviorV34Label[] = [
    BehaviorV34Label.READ,
    BehaviorV34Label.WRITE,
    BehaviorV34Label.PHONE_INTERACTION,
    BehaviorV34Label.NO_VISIBLE_STUDY
  ];

  static decode(logits: number[]): BehaviorV34Result {
    if (logits.length !== BehaviorV34Decision.LABELS.length) {
      return BehaviorV34Decision.rejected();
    }
    let maxLogit: number = -Number.MAX_VALUE;
    for (let i: number = 0; i < logits.length; i++) {
      if (!Number.isFinite(logits[i])) return BehaviorV34Decision.rejected();
      maxLogit = Math.max(maxLogit, logits[i] / BehaviorV34Decision.TEMPERATURE);
    }
    const probabilities: number[] = [];
    let sum: number = 0;
    for (let i: number = 0; i < logits.length; i++) {
      const value: number = Math.exp(logits[i] / BehaviorV34Decision.TEMPERATURE - maxLogit);
      probabilities.push(value);
      sum += value;
    }
    let bestIndex: number = 0;
    let best: number = -1;
    let second: number = -1;
    for (let i: number = 0; i < probabilities.length; i++) {
      probabilities[i] = probabilities[i] / sum;
      if (probabilities[i] > best) {
        second = best;
        best = probabilities[i];
        bestIndex = i;
      } else if (probabilities[i] > second) {
        second = probabilities[i];
      }
    }
    const margin: number = best - second;
    const accepted: boolean = best >= BehaviorV34Decision.MIN_CONFIDENCE &&
      margin >= BehaviorV34Decision.MIN_MARGIN;
    return {
      label: accepted ? BehaviorV34Decision.LABELS[bestIndex] : BehaviorV34Label.CONTINUE_OBSERVING,
      confidence: best,
      margin: margin,
      isStable: accepted,
      probabilities: probabilities.slice()
    };
  }

  private static rejected(): BehaviorV34Result {
    return {
      label: BehaviorV34Label.CONTINUE_OBSERVING,
      confidence: 0,
      margin: 0,
      isStable: false,
      probabilities: []
    };
  }
}

export class BehaviorReminderTracker {
  private phoneSince: number = -1;
  private lastPhoneSeenAt: number = -1;
  private lastPhoneReminderAt: number = -1;
  private noStudySince: number = -1;
  private reminderText: string = '';
  private reminderKind: string = '';

  process(result: BehaviorV34Result, timestamp: number): string {
    if (!result.isStable || result.label === BehaviorV34Label.CONTINUE_OBSERVING) {
      return this.reminderText;
    }
    if (result.label === BehaviorV34Label.READ ||
      result.label === BehaviorV34Label.WRITE ||
      result.label === BehaviorV34Label.COMPUTER) {
      this.phoneSince = -1;
      this.noStudySince = -1;
      if (this.reminderKind === 'PHONE' && timestamp - this.lastPhoneSeenAt >= 1000) {
        this.reminderText = '';
        this.reminderKind = '';
      } else if (this.reminderKind === 'NO_STUDY') {
        this.reminderText = '';
        this.reminderKind = '';
      }
      return this.reminderText;
    }
    if (result.label === BehaviorV34Label.PHONE_INTERACTION) {
      this.noStudySince = -1;
      this.lastPhoneSeenAt = timestamp;
      if (this.phoneSince < 0) this.phoneSince = timestamp;
      if (timestamp - this.phoneSince >= 3000 &&
        (this.lastPhoneReminderAt < 0 || timestamp - this.lastPhoneReminderAt >= 600000)) {
        this.reminderText = '检测到持续手机交互，请确认它是否与当前学习任务有关。';
        this.reminderKind = 'PHONE';
        this.lastPhoneReminderAt = timestamp;
      }
      return this.reminderText;
    }
    this.phoneSince = -1;
    if (this.noStudySince < 0) this.noStudySince = timestamp;
    if (timestamp - this.noStudySince >= 20000) {
      this.reminderText = '暂时未观察到明确学习行为，可以把注意力拉回当前任务。';
      this.reminderKind = 'NO_STUDY';
    }
    return this.reminderText;
  }

  current(): string { return this.reminderText; }

  reset(): void {
    this.phoneSince = -1;
    this.lastPhoneSeenAt = -1;
    this.lastPhoneReminderAt = -1;
    this.noStudySince = -1;
    this.reminderText = '';
    this.reminderKind = '';
  }
}
