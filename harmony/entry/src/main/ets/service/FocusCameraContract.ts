export interface PersonBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

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

export class FocusCameraRunToken {
  private version: number = 0;
  private shouldRun: boolean = false;

  beginStart(): number {
    this.shouldRun = true;
    this.version += 1;
    return this.version;
  }

  stop(): void {
    this.shouldRun = false;
    this.version += 1;
  }

  isCurrent(version: number): boolean {
    return this.shouldRun && this.version === version;
  }

  desired(): boolean {
    return this.shouldRun;
  }
}

export class FocusCameraActivationPolicy {
  static shouldRun(focusMode: string, sessionMode: string): boolean {
    return focusMode === 'focus' && sessionMode === 'SMART_GUARD';
  }
}

export class FocusCameraLifecycleEvent {
  static readonly START: string = 'START';
  static readonly RESUME: string = 'RESUME';
  static readonly PAUSE: string = 'PAUSE';
  static readonly FINISH: string = 'FINISH';
  static readonly HIDE: string = 'HIDE';
  static readonly LEAVE: string = 'LEAVE';
  static readonly RESET: string = 'RESET';
}

export class FocusCameraLifecycleAction {
  static readonly START: string = 'START';
  static readonly STOP: string = 'STOP';
}

export class FocusCameraLifecyclePolicy {
  static action(event: string, focusMode: string, sessionMode: string): string {
    const sessionCanStart: boolean = event === FocusCameraLifecycleEvent.START ||
      event === FocusCameraLifecycleEvent.RESUME;
    return sessionCanStart && FocusCameraActivationPolicy.shouldRun(focusMode, sessionMode) ?
      FocusCameraLifecycleAction.START : FocusCameraLifecycleAction.STOP;
  }

  static shouldResetSummary(event: string, focusMode: string): boolean {
    return event === FocusCameraLifecycleEvent.START && focusMode === 'focus';
  }

  static shouldResumeOnForeground(sessionStatus: string, focusMode: string,
    sessionMode: string): boolean {
    return sessionStatus === 'active' && FocusCameraActivationPolicy.shouldRun(focusMode, sessionMode);
  }
}

export class FocusCameraSignalPresentation {
  static shouldPresent(isStable: boolean, cameraState: string): boolean {
    return isStable && cameraState === FocusCameraState.RUNNING;
  }

  static label(label: string, isStable: boolean): string {
    return isStable ? label : '';
  }

  static confidence(confidence: number, isStable: boolean): number {
    return isStable && Number.isFinite(confidence) ? confidence : 0;
  }
}

export class FocusBehaviorLabelText {
  static describe(label: string): string {
    if (label === 'READ') return '阅读';
    if (label === 'WRITE') return '书写';
    if (label === 'PHONE_INTERACTION') return '使用手机';
    if (label === 'COMPUTER') return '使用电脑';
    if (label === 'NO_VISIBLE_STUDY') return '未观察到学习行为';
    return '';
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
      const box: DetectionBoundingBox = candidate.boundingBox;
      if (!Number.isFinite(candidate.score) || !Number.isFinite(box.left) ||
        !Number.isFinite(box.top) || !Number.isFinite(box.width) || !Number.isFinite(box.height) ||
        candidate.score < PersonRoiSelector.MIN_SCORE ||
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

/** Converts repeated no-person detections into one event per sustained absence. */
export class PersonAbsenceTracker {
  static readonly DEFAULT_GRACE_MS: number = 5000;
  static readonly DEFAULT_RECOVERY_MS: number = 1000;
  private readonly graceMs: number;
  private readonly recoveryMs: number;
  private missingSince: number = -1;
  private presentSince: number = -1;
  private confirmed: boolean = false;

  constructor(graceMs: number = PersonAbsenceTracker.DEFAULT_GRACE_MS,
    recoveryMs: number = PersonAbsenceTracker.DEFAULT_RECOVERY_MS) {
    this.graceMs = Math.max(0, graceMs);
    this.recoveryMs = Math.max(0, recoveryMs);
  }

  process(personPresent: boolean, timestamp: number): boolean {
    if (personPresent) {
      if (!this.confirmed) {
        this.reset();
      } else if (this.presentSince < 0) {
        this.presentSince = timestamp;
      } else if (timestamp - this.presentSince >= this.recoveryMs) {
        this.reset();
      }
      return false;
    }
    this.presentSince = -1;
    if (this.missingSince < 0) {
      this.missingSince = timestamp;
      return false;
    }
    if (!this.confirmed && timestamp - this.missingSince >= this.graceMs) {
      this.confirmed = true;
      return true;
    }
    return false;
  }

  reset(): void {
    this.missingSince = -1;
    this.presentSince = -1;
    this.confirmed = false;
  }

  /** Clears incomplete timing without allowing one continuous confirmed absence to count again. */
  suspend(): void {
    this.missingSince = -1;
    this.presentSince = -1;
  }
}

export class FrameAnalysisGate {
  private readonly intervalMs: number;
  private inFlight: boolean = false;
  private lastStartedAt: number = Number.NEGATIVE_INFINITY;

  constructor(intervalMs: number = 500) {
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
