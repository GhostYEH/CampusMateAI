import type { PersonBox } from './FocusAssistProvider';

export interface DetectionBoundingBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface DetectionCandidate {
  labels: number[];
  score: number;
  boundingBox: DetectionBoundingBox;
}

export class FocusCameraState {
  static readonly STOPPED: string = 'STOPPED';
  static readonly STARTING: string = 'STARTING';
  static readonly RUNNING: string = 'RUNNING';
  static readonly WAITING_FOR_PERSON: string = 'WAITING_FOR_PERSON';
  static readonly PERMISSION_DENIED: string = 'PERMISSION_DENIED';
  static readonly UNAVAILABLE: string = 'UNAVAILABLE';
  static readonly ERROR: string = 'ERROR';
}

export class FocusCameraStateText {
  static describe(state: string): string {
    if (state === FocusCameraState.STARTING) return '正在启动本地相机与人体检测';
    if (state === FocusCameraState.RUNNING) return 'V3.4 正在本地识别学习状态';
    if (state === FocusCameraState.WAITING_FOR_PERSON) return '相机已启用，等待检测到学生人体';
    if (state === FocusCameraState.PERMISSION_DENIED) return '未获得相机权限，行为提醒已停用';
    if (state === FocusCameraState.ERROR) return '本帧处理失败，行为提醒未触发';
    if (state === FocusCameraState.UNAVAILABLE) return '当前设备不支持本地相机行为识别';
    return '开始专注后启用本地学习状态辅助';
  }
}

export class PersonRoiSelector {
  static readonly PERSON_LABEL: number = 13;
  static readonly MIN_SCORE: number = 0.50;

  static select(candidates: DetectionCandidate[], frameWidth: number,
    frameHeight: number): PersonBox | undefined {
    if (frameWidth < 2 || frameHeight < 2) {
      return undefined;
    }
    let best: DetectionCandidate | undefined = undefined;
    for (const candidate of candidates) {
      if (candidate.score < PersonRoiSelector.MIN_SCORE ||
        !candidate.labels.includes(PersonRoiSelector.PERSON_LABEL)) {
        continue;
      }
      if (best === undefined || candidate.score > best.score) {
        best = candidate;
      }
    }
    if (best === undefined) {
      return undefined;
    }
    const left: number = Math.max(0, Math.min(frameWidth, best.boundingBox.left));
    const top: number = Math.max(0, Math.min(frameHeight, best.boundingBox.top));
    const right: number = Math.max(0, Math.min(frameWidth,
      best.boundingBox.left + best.boundingBox.width));
    const bottom: number = Math.max(0, Math.min(frameHeight,
      best.boundingBox.top + best.boundingBox.height));
    if (right - left < 2 || bottom - top < 2) {
      return undefined;
    }
    return { left: left, top: top, right: right, bottom: bottom };
  }
}

export class FrameAnalysisGate {
  private readonly intervalMs: number;
  private inFlight: boolean = false;
  private lastStartedAt: number = Number.NEGATIVE_INFINITY;

  constructor(intervalMs: number = 1000) {
    this.intervalMs = Math.max(0, intervalMs);
  }

  tryAcquire(timestamp: number): boolean {
    if (this.inFlight || timestamp - this.lastStartedAt < this.intervalMs) {
      return false;
    }
    this.inFlight = true;
    this.lastStartedAt = timestamp;
    return true;
  }

  release(): void {
    this.inFlight = false;
  }

  reset(): void {
    this.inFlight = false;
    this.lastStartedAt = Number.NEGATIVE_INFINITY;
  }
}
