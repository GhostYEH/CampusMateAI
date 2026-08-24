export enum BehaviorV34Label {
  READ = 'READ',
  WRITE = 'WRITE',
  PHONE_INTERACTION = 'PHONE_INTERACTION',
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
      probabilities: probabilities
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
  private noStudySince: number = -1;
  private reminderText: string = '';

  process(result: BehaviorV34Result, timestamp: number): string {
    if (!result.isStable || result.label === BehaviorV34Label.CONTINUE_OBSERVING) {
      return this.reminderText;
    }
    if (result.label === BehaviorV34Label.READ || result.label === BehaviorV34Label.WRITE) {
      this.reset();
      return '';
    }
    if (result.label === BehaviorV34Label.PHONE_INTERACTION) {
      this.noStudySince = -1;
      if (this.phoneSince < 0) this.phoneSince = timestamp;
      if (timestamp - this.phoneSince >= 3000) {
        this.reminderText = '检测到持续手机交互，请确认它是否与当前学习任务有关。';
      }
      return this.reminderText;
    }
    this.phoneSince = -1;
    if (this.noStudySince < 0) this.noStudySince = timestamp;
    if (timestamp - this.noStudySince >= 20000) {
      this.reminderText = '暂时未观察到明确学习行为，可以把注意力拉回当前任务。';
    }
    return this.reminderText;
  }

  current(): string { return this.reminderText; }

  reset(): void {
    this.phoneSince = -1;
    this.noStudySince = -1;
    this.reminderText = '';
  }
}
