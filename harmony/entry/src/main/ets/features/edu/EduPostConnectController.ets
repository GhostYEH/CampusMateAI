import { EduBindingDto, EduSyncResult } from '../../data/ApiClient';
import {
  EduConnectionRequestGuard,
  EduPostConnectRequestToken
} from './EduConnectionRequestGuard';

export interface EduPostConnectOperations {
  getBinding(): Promise<EduBindingDto | undefined>;
  syncSchedule(): Promise<EduSyncResult>;
  syncGrade(): Promise<EduSyncResult>;
}

export interface EduPostConnectStateWriter {
  setBinding(binding: EduBindingDto | null): void;
  setSyncing(syncing: boolean): void;
  setSyncMessage(message: string): void;
}

/** Runs binding and sync requests inside one connection-scoped lifecycle. */
export class EduPostConnectController {
  private guard: EduConnectionRequestGuard;
  private operations: EduPostConnectOperations;
  private state: EduPostConnectStateWriter;

  constructor(
    guard: EduConnectionRequestGuard,
    operations: EduPostConnectOperations,
    state: EduPostConnectStateWriter
  ) {
    this.guard = guard;
    this.operations = operations;
    this.state = state;
  }

  private isCurrent(request: EduPostConnectRequestToken): boolean {
    return this.guard.isPostConnectCurrent(request);
  }

  async loadBinding(request: EduPostConnectRequestToken): Promise<void> {
    if (!this.isCurrent(request)) return;
    try {
      if (!this.isCurrent(request)) return;
      const binding: EduBindingDto | undefined = await this.operations.getBinding();
      if (!this.isCurrent(request)) return;
      this.state.setBinding(binding || null);
    } catch (_error) {
      // Initial and stale binding failures stay silent.
    }
  }

  async onConnected(request: EduPostConnectRequestToken): Promise<void> {
    if (!this.isCurrent(request)) return;
    if (!this.isCurrent(request)) return;
    await this.loadBinding(request);
    if (!this.isCurrent(request)) return;
    if (!this.isCurrent(request)) return;
    await this.autoSync(request);
    if (!this.isCurrent(request)) return;
  }

  async autoSync(request: EduPostConnectRequestToken): Promise<void> {
    if (!this.isCurrent(request)) return;
    this.state.setSyncing(true);
    if (!this.isCurrent(request)) return;
    this.state.setSyncMessage('正在同步课表…');
    try {
      if (!this.isCurrent(request)) return;
      const scheduleResult: EduSyncResult = await this.operations.syncSchedule();
      if (!this.isCurrent(request)) return;
      this.state.setSyncMessage('正在同步成绩…');
      if (!this.isCurrent(request)) return;
      const gradeResult: EduSyncResult = await this.operations.syncGrade();
      if (!this.isCurrent(request)) return;
      const scheduleOk: boolean = scheduleResult.status === 'success';
      const gradeOk: boolean = gradeResult.status === 'success';
      if (!this.isCurrent(request)) return;
      this.state.setSyncMessage(
        `课表同步${scheduleOk ? '成功' : '失败'}，成绩同步${gradeOk ? '成功' : '失败'}`
      );
      if (!this.isCurrent(request)) return;
      await this.loadBinding(request);
      if (!this.isCurrent(request)) return;
    } catch (error) {
      if (!this.isCurrent(request)) return;
      this.state.setSyncMessage('同步失败: ' + String(error).substring(0, 100));
    } finally {
      if (this.isCurrent(request)) this.state.setSyncing(false);
    }
  }
}

export function invalidateEduConnectionLifecycle(
  guard: EduConnectionRequestGuard,
  stopPolling: () => void,
  clearState: () => void
): number {
  stopPolling();
  const generation: number = guard.invalidate();
  clearState();
  return generation;
}
