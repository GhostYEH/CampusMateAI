import { FocusMode } from '../../data/Models';

export type FocusLobbyStep = 'GREETING' | 'ASK_DURATION' | 'ASK_MODE' | 'CONFIRM';
export type FocusRobotState = 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'HAPPY' | 'ERROR';
export type FocusSessionAction = 'pause' | 'resume' | 'finish';

export class FocusPresentationState {
  static nextLobbyStep(step: FocusLobbyStep): FocusLobbyStep {
    if (step === 'ASK_DURATION') {
      return 'ASK_MODE';
    }
    if (step === 'ASK_MODE') {
      return 'CONFIRM';
    }
    return step;
  }

  static formatDuration(seconds: number): string {
    const total: number = Math.max(0, Math.floor(seconds));
    const minutes: number = Math.floor(total / 60);
    const remaining: string = (total % 60).toString().padStart(2, '0');
    return minutes > 0 ? `${minutes} 分 ${remaining} 秒` : `${total} 秒`;
  }

  static durationSeconds(minutes: number): number {
    return Math.min(240, Math.max(5, Math.floor(minutes))) * 60;
  }

  static shouldShowObservation(mode: FocusMode, status: string, sessionMode: string): boolean {
    return mode === 'focus' && status.length > 0 && sessionMode === 'SMART_GUARD';
  }

  static robotStateForVoice(phase: string): FocusRobotState {
    if (phase === 'LISTENING') return 'LISTENING';
    if (phase === 'THINKING') return 'THINKING';
    if (phase === 'SPEAKING') return 'SPEAKING';
    if (phase === 'ERROR') return 'ERROR';
    return 'IDLE';
  }

  static robotStatusText(state: FocusRobotState): string {
    if (state === 'LISTENING') return '我在听';
    if (state === 'THINKING') return '让我想想';
    if (state === 'SPEAKING') return '正在回答你';
    if (state === 'HAPPY') return '做得很好';
    if (state === 'ERROR') return '暂时无法连接';
    return '我会陪你开始这段专注';
  }
}

export class FocusSessionActionGate {
  private pending: boolean = false;

  tryStart(): boolean {
    if (this.pending) return false;
    this.pending = true;
    return true;
  }

  complete(): void {
    this.pending = false;
  }
}

export class FocusCountdownRunToken {
  private version: number = 0;
  private active: boolean = false;

  begin(): number {
    this.version += 1;
    this.active = true;
    return this.version;
  }

  cancel(): void {
    this.active = false;
    this.version += 1;
  }

  isCurrent(version: number): boolean {
    return this.active && this.version === version;
  }
}
