import { BehaviorSessionSummary, BehaviorV34Label } from './BehaviorV34Decision';
import { PersonBox } from './FocusCameraContract';
import { StudyBehaviorSummary } from '../data/Models';

export function toStudyBehaviorSummary(
  summary: BehaviorSessionSummary | undefined
): StudyBehaviorSummary | undefined {
  if (summary === undefined) return undefined;
  const request: StudyBehaviorSummary = {
    observed_seconds: summary.observed_seconds,
    study_seconds: summary.study_seconds,
    paused_seconds: summary.paused_seconds,
    longest_continuous_study_seconds: summary.longest_continuous_study_seconds,
    meaningful_switch_count: summary.meaningful_switch_count,
    phone_interaction_count: summary.phone_interaction_count,
    possible_distraction_count: summary.possible_distraction_count,
    absent_count: summary.absent_count,
    reminder_count: summary.reminder_count,
    model_version: summary.model_version
  };
  return request;
}

export enum FocusAssistStatus {
  AVAILABLE = 'AVAILABLE',
  RUNNING = 'RUNNING',
  UNAVAILABLE = 'UNAVAILABLE',
  ERROR = 'ERROR'
}

export interface FocusAssistSignal {
  label: BehaviorV34Label;
  confidence: number;
  isStable: boolean;
  timestamp: number;
  modelVersion: string;
}

export interface RgbaBehaviorFrame {
  pixels: Uint8Array;
  width: number;
  height: number;
  personBox: PersonBox;
  timestamp: number;
}

export interface FocusAssistProvider {
  available(): boolean;
  status(): FocusAssistStatus;
  resetSessionSummary(startedAt?: number): void;
  recordAbsence(): void;
  start(): Promise<void>;
  stop(): Promise<void>;
  analyze(frame: RgbaBehaviorFrame): Promise<FocusAssistSignal | undefined>;
  latestSignal(): FocusAssistSignal | undefined;
  currentReminder(): string;
  sessionSummary(): BehaviorSessionSummary | undefined;
  detail(): string;
}

/**
 * Safe behavior-recognition fallback when the local model or person-ROI frame
 * pipeline is unavailable. It never fabricates an inference result.
 */
export class UnavailableFocusAssistProvider implements FocusAssistProvider {
  available(): boolean { return false; }
  status(): FocusAssistStatus { return FocusAssistStatus.UNAVAILABLE; }
  resetSessionSummary(_startedAt?: number): void { return; }
  recordAbsence(): void { return; }
  async start(): Promise<void> { return; }
  async stop(): Promise<void> { return; }
  async analyze(_frame: RgbaBehaviorFrame): Promise<FocusAssistSignal | undefined> { return undefined; }
  latestSignal(): FocusAssistSignal | undefined { return undefined; }
  currentReminder(): string { return ''; }
  sessionSummary(): BehaviorSessionSummary | undefined { return undefined; }
  detail(): string { return '当前设备暂不支持本地学习状态辅助'; }
}
