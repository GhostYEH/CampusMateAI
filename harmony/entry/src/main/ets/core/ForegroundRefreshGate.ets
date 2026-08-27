export class ForegroundRefreshGate {
  private readonly minimumIntervalMs: number;
  private visible: boolean = true;
  private running: boolean = false;
  private lastStartedAt: number = -1;

  constructor(minimumIntervalMs: number) {
    this.minimumIntervalMs = Math.max(0, minimumIntervalMs);
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
  }

  isVisible(): boolean {
    return this.visible;
  }

  tryStart(nowMs: number): boolean {
    if (!this.visible || this.running) return false;
    if (this.lastStartedAt >= 0 && nowMs - this.lastStartedAt < this.minimumIntervalMs) return false;
    this.running = true;
    this.lastStartedAt = nowMs;
    return true;
  }

  finish(): void {
    this.running = false;
  }

  reset(): void {
    this.running = false;
    this.lastStartedAt = -1;
  }
}
