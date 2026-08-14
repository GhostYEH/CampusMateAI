export enum FocusAssistStatus {
  AVAILABLE = 'AVAILABLE',
  RUNNING = 'RUNNING',
  UNAVAILABLE = 'UNAVAILABLE',
  ERROR = 'ERROR'
}

export interface FocusAssistSignal {
  label: string;
  confidence: number;
  isStable: boolean;
  timestamp: number;
  modelVersion: string;
}

export interface FocusAssistProvider {
  available(): boolean;
  status(): FocusAssistStatus;
  start(): Promise<void>;
  stop(): Promise<void>;
  latestSignal(): FocusAssistSignal | undefined;
  detail(): string;
}

/**
 * Safe production fallback until the Android expression model and its exact
 * preprocessing/output contract are proven on a HarmonyOS API 24 inference runtime.
 */
export class UnavailableFocusAssistProvider implements FocusAssistProvider {
  available(): boolean { return false; }
  status(): FocusAssistStatus { return FocusAssistStatus.UNAVAILABLE; }
  async start(): Promise<void> { return; }
  async stop(): Promise<void> { return; }
  latestSignal(): FocusAssistSignal | undefined { return undefined; }
  detail(): string { return '当前设备暂不支持本地学习状态辅助'; }
}
