import { EduBindingDto, EduScheduleItemsResponse, EduSyncResult } from '../../data/ApiClient';
import {
  EduConnectionRequestGuard,
  EduPostConnectRequestToken
} from './EduConnectionRequestGuard';

export interface EduPostConnectOperations {
  getBinding(): Promise<EduBindingDto | undefined>;
  syncSchedule(): Promise<EduSyncResult>;
  syncGrade(): Promise<EduSyncResult>;
  syncExam(): Promise<EduSyncResult>;
  listScheduleItems(semester?: string): Promise<EduScheduleItemsResponse>;
}

export interface EduPostConnectStateWriter {
  setBinding(binding: EduBindingDto | null): void;
  setSyncing(syncing: boolean): void;
  setSyncMessage(message: string): void;
}

const SCHEDULE_STAGE_LABELS: Record<string, string> = {
  'protocol_discovery': '课表协议识别',
  'fetch': '课表读取',
  'parse': '课表解析',
  'validate': '课表校验',
  'commit': '课表保存'
};

export function isVerifiedScheduleImport(
  result: EduSyncResult,
  stored: EduScheduleItemsResponse | undefined
): boolean {
  if (result.status !== 'success' || result.persisted !== true || stored === undefined) return false;
  if (result.items_count === 0) return result.stage === 'commit' && stored.items_count === 0;
  return stored.items_count >= result.items_count;
}

export function eduScheduleStatusMessage(result: EduSyncResult, imported: boolean): string {
  if (imported) {
    return result.items_count === 0 ? '课表同步成功，本学期暂无课程' :
      `课表同步成功，已校验并保存 ${result.items_count} 条课程记录`;
  }
  if (result.status === 'failed') {
    const label: string | undefined = result.stage === undefined ? undefined : SCHEDULE_STAGE_LABELS[result.stage];
    const prefix: string = label === undefined ? '' : `${label}失败：`;
    const detail: string = result.error_message || '请稍后重试';
    const preserved: string = result.previous_schedule_preserved === true ? '；原有课表未被覆盖' : '';
    return `${prefix}${detail}${preserved}`;
  }
  return '课表未成功导入系统，请重新同步；原有课表未被覆盖';
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
      let storedSchedule: EduScheduleItemsResponse | undefined = undefined;
      if (scheduleResult.status === 'success') {
        storedSchedule = await this.operations.listScheduleItems(
          scheduleResult.schedule?.semester || scheduleResult.semester
        );
      }
      if (!this.isCurrent(request)) return;
      this.state.setSyncMessage('正在同步成绩…');
      if (!this.isCurrent(request)) return;
      const gradeResult: EduSyncResult = await this.operations.syncGrade();
      if (!this.isCurrent(request)) return;
      this.state.setSyncMessage('正在同步考试安排…');
      if (!this.isCurrent(request)) return;
      const examResult: EduSyncResult = await this.operations.syncExam();
      if (!this.isCurrent(request)) return;
      const scheduleOk: boolean = isVerifiedScheduleImport(scheduleResult, storedSchedule);
      const gradeOk: boolean = gradeResult.status === 'success';
      const examOk: boolean = examResult.status === 'success';
      if (!this.isCurrent(request)) return;
      this.state.setSyncMessage(
        `${eduScheduleStatusMessage(scheduleResult, scheduleOk)}，成绩同步${gradeOk ? '成功' : '失败'}，考试同步${examOk ? '成功' : '失败'}`
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
