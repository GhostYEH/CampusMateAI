import { BehaviorSessionSummary, BehaviorV34Label } from './BehaviorV34Decision';
import { PersonBox } from './FocusCameraContract';

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
  async start(): Promise<void> { return; }
  async stop(): Promise<void> { return; }
  async analyze(_frame: RgbaBehaviorFrame): Promise<FocusAssistSignal | undefined> { return undefined; }
  latestSignal(): FocusAssistSignal | undefined { return undefined; }
  currentReminder(): string { return ''; }
  sessionSummary(): BehaviorSessionSummary | undefined { return undefined; }
  detail(): string { return '当前设备暂不支持本地学习状态辅助'; }
}
