import { AgentRuntimeRepository } from '../../repository/AgentRuntimeRepository';
import {
  AgentJob, AgentRun, LearningPlanSummary, StudentGoal, RunStatus, AgentEnumParser
} from '../../data/AgentRuntimeModels';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SseEvent } from '../../data/ApiClient';

// 学习目标执行中心：目标→计划草案→确认/创建待办→阶段总结→重规划。
// 所有决策与风险判断由服务端完成，鸿蒙端只负责请求、展示和生命周期控制。
@Component
export struct GoalExecutionPage {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  repository: AgentRuntimeRepository | null = null;
  onBack: () => void = () => {};
  @State goals: StudentGoal[] = [];
  @State jobs: AgentJob[] = [];
  @State selectedGoalId: string = '';
  @State goalName: string = '';
  @State minutesText: string = '60';
  @State planId: string = '';
  @State summary: LearningPlanSummary | null = null;
  @State activeRunId: string = '';
  @State liveStatus: RunStatus = RunStatus.UNKNOWN;
  @State loading: boolean = false;
  @State error: string = '';
  private observedRunId: string = '';

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  async aboutToAppear(): Promise<void> {
    await this.reload();
  }

  async reload(): Promise<void> {
    if (this.repository === null) return;
    try {
      const goals: StudentGoal[] = await this.repository.listLearningGoals();
      const jobs: AgentJob[] = await this.repository.listJobs();
      this.goals = goals;
      this.jobs = jobs.filter((job: AgentJob) => job.job_kind === 'learning_goal');
      if (this.selectedGoalId.length === 0 && goals.length > 0) this.selectedGoalId = goals[0].goal_id;
      const latest: AgentJob | undefined = this.jobs.find((job: AgentJob) => {
        return job.input_ref !== undefined && (job.input_ref['goal_id'] as string) === this.selectedGoalId;
      });
      if (latest !== undefined && latest.latest_run_id !== null) {
        this.activeRunId = latest.latest_run_id;
        this.liveStatus = latest.status;
        if (latest.status === RunStatus.QUEUED || latest.status === RunStatus.RUNNING) {
          this.subscribeRun(latest.latest_run_id, latest.job_id);
        } else {
          await this.loadPlanFromJob(latest);
        }
      }
    } catch (_) {
      this.error = '目标数据加载失败，请重试';
    }
  }

  minutes(): number {
    const parsed: number = Number.parseInt(this.minutesText, 10);
    if (Number.isNaN(parsed)) return 60;
    return Math.max(1, Math.min(1440, parsed));
  }

  async createGoal(): Promise<void> {
    if (this.repository === null || this.goalName.trim().length === 0 || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      const goal: StudentGoal = await this.repository.createLearningGoal(this.goalName.trim());
      this.goals = [...this.goals, goal];
      this.selectedGoalId = goal.goal_id;
      this.goalName = '';
    } catch (_) {
      this.error = '创建学习目标失败，请重试';
    } finally {
      this.loading = false;
    }
  }

  async generatePlan(): Promise<void> {
    if (this.repository === null || this.selectedGoalId.length === 0 || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      const job: AgentJob = await this.repository.createLearningGoalJob(this.selectedGoalId, this.minutes());
      this.jobs = [job, ...this.jobs.filter((item: AgentJob) => item.job_id !== job.job_id)];
      this.activeRunId = job.latest_run_id ?? '';
      this.liveStatus = job.status;
      this.planId = '';
      this.summary = null;
      if (job.latest_run_id !== null) this.subscribeRun(job.latest_run_id, job.job_id);
    } catch (_) {
      this.error = '生成计划草案失败，请检查目标数据后重试';
    } finally {
      this.loading = false;
    }
  }

  async decidePlan(decision: string): Promise<void> {
    if (this.repository === null || this.planId.length === 0 || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      await this.repository.decidePlan(this.planId, decision);
      this.summary = await this.repository.getPlanSummary(this.planId);
      await this.reload();
    } catch (_) {
      this.error = decision === 'ACCEPT' ? '创建待办失败，请重试' : '计划决策失败，请重试';
    } finally {
      this.loading = false;
    }
  }

  async executePlan(): Promise<void> {
    if (this.repository === null || this.planId.length === 0 || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      await this.repository.executePlan(this.planId);
      this.summary = await this.repository.getPlanSummary(this.planId);
      await this.reload();
    } catch (_) {
      this.error = '创建个人待办失败，请重试';
    } finally {
      this.loading = false;
    }
  }

  async replan(): Promise<void> {
    if (this.repository === null || this.planId.length === 0 || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      this.planId = await this.repository.replan(this.planId);
      this.summary = await this.repository.getPlanSummary(this.planId);
      await this.reload();
    } catch (_) {
      this.error = '重新规划失败，请稍后重试';
    } finally {
      this.loading = false;
    }
  }

  async control(run: AgentRun, action: string): Promise<void> {
    if (this.repository === null || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      if (action === 'pause') await this.repository.pauseRun(run.run_id, '学生在目标中心暂停');
      else if (action === 'resume') await this.repository.resumeRun(run.run_id);
      else await this.repository.retryRun(run.run_id);
      await this.reload();
    } catch (_) {
      this.error = '运行控制失败，请刷新后重试';
    } finally {
      this.loading = false;
    }
  }

  private async loadPlanFromJob(job: AgentJob): Promise<void> {
    if (this.repository === null) return;
    const rawPlanId: Object | undefined = job.input_ref === undefined ? undefined : job.input_ref['plan_id'];
    const nextPlanId: string = rawPlanId === undefined || rawPlanId === null ? '' : rawPlanId as string;
    if (nextPlanId.length === 0) {
      this.planId = '';
      this.summary = null;
      return;
    }
    this.planId = nextPlanId;
    this.summary = await this.repository.getPlanSummary(nextPlanId);
  }

  subscribeRun(runId: string, jobId: string): void {
    if (this.repository === null || runId.length === 0 || this.observedRunId === runId) return;
    this.observedRunId = runId;
    this.repository.streamEvents(runId, '', (event: SseEvent) => {
      if (this.activeRunId !== runId) return;
      try {
        const raw: Record<string, Object> = JSON.parse(event.data) as Record<string, Object>;
        const status: RunStatus = AgentEnumParser.runStatus((raw.status ?? '') as string);
        this.liveStatus = status;
        if (status === RunStatus.SUCCEEDED) {
          this.finishRun(runId, jobId, true);
        } else if (status === RunStatus.FAILED || status === RunStatus.CANCELLED) {
          this.error = status === RunStatus.CANCELLED ? '任务已取消，可重新生成计划' : '计划生成失败，可稍后重试';
        }
      } catch (_) { /* 忽略无法解析的事件，不中断页面 */ }
    }).catch(() => {
      if (this.activeRunId === runId) this.error = '事件流中断，可刷新重试';
    });
  }

  private async finishRun(runId: string, jobId: string, succeeded: boolean): Promise<void> {
    if (this.repository === null || this.activeRunId !== runId || !succeeded) return;
    try {
      const completed: AgentJob = await this.repository.getJob(jobId);
      this.jobs = this.jobs.map((item: AgentJob) => item.job_id === jobId ? completed : item);
      await this.loadPlanFromJob(completed);
      if (this.planId.length === 0) this.error = '任务已完成，但计划引用暂不可用，请刷新重试';
    } catch (_) {
      this.error = '任务已完成，但结果加载失败，请重试';
    }
  }

  statusLabel(status: RunStatus): string {
    switch (status) {
      case RunStatus.QUEUED: return '排队中';
      case RunStatus.RUNNING: return '执行中';
      case RunStatus.PAUSED: return '已暂停';
      case RunStatus.SUCCEEDED: return '已完成';
      case RunStatus.PARTIAL: return '部分完成';
      case RunStatus.FAILED: return '失败';
      case RunStatus.CANCELLED: return '已取消';
      default: return '状态待确认';
    }
  }

  @Builder SummaryCard() {
    if (this.summary !== null) {
      Column({ space: 5 }) {
        Text(this.summary.headline).fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Medium)
        Text(`阶段：${this.summary.stage} · 完成度 ${this.summary.completion_percent}%`)
          .fontColor(this.palette().muted).fontSize(12)
        Text(`已执行 ${this.summary.executed_item_count}/${this.summary.planned_item_count} 项 · 预计 ${this.summary.planned_minutes} 分钟`)
          .fontColor(this.palette().muted).fontSize(12)
        Text(`下一步：${this.summary.next_action}`).fontColor(this.palette().primary).fontSize(12)
        ForEach(this.summary.recommendations, (item: string) => {
          Text(`• ${item}`).fontColor(this.palette().muted).fontSize(11)
        }, (item: string) => item)
      }.width('100%').padding(12)
        .backgroundColor(this.palette().glass.surface)
        .border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
    }
  }

  @Builder RunCard(job: AgentJob) {
    Column({ space: 6 }) {
      Row() {
        Text(job.input_ref['plan_id'] === undefined ? '目标计划' : '学习计划')
          .fontColor(this.palette().text).fontSize(13).layoutWeight(1)
        Text(this.statusLabel(job.latest_run_id === this.activeRunId && this.liveStatus !== RunStatus.UNKNOWN
          ? this.liveStatus : job.status))
          .fontColor(this.palette().primary).fontSize(11)
      }.width('100%')
      Text(`更新于 ${job.updated_at}`).fontColor(this.palette().muted).fontSize(10)
      if (job.latest_run_id !== null && (job.status === RunStatus.RUNNING || job.status === RunStatus.QUEUED || job.status === RunStatus.PAUSED || job.status === RunStatus.FAILED || job.status === RunStatus.PARTIAL || job.status === RunStatus.CANCELLED)) {
        Row({ space: 8 }) {
          if (job.status === RunStatus.RUNNING || job.status === RunStatus.QUEUED) {
            Button('暂停').height(32).layoutWeight(1).onClick(() => this.control({ run_id: job.latest_run_id!, status: job.status } as AgentRun, 'pause'))
          }
          if (job.status === RunStatus.PAUSED) {
            Button('恢复').height(32).layoutWeight(1).onClick(() => this.control({ run_id: job.latest_run_id!, status: job.status } as AgentRun, 'resume'))
          }
          if (job.status === RunStatus.FAILED || job.status === RunStatus.PARTIAL || job.status === RunStatus.CANCELLED) {
            Button('重试').height(32).layoutWeight(1).onClick(() => this.control({ run_id: job.latest_run_id!, status: job.status } as AgentRun, 'retry'))
          }
        }.width('100%')
      }
    }.width('100%').padding(12)
      .backgroundColor(this.palette().glass.surface)
      .border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
  }

  build() {
    Column() {
      SecondaryHeader({ title: 'AI目标执行中心', subtitle: '目标、计划、待办与阶段跟进', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 14 }) {
          if (this.error.length > 0) Text(this.error).fontColor(this.palette().danger).fontSize(12)
          Text('创建学习目标').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
          Row({ space: 8 }) {
            TextInput({ text: this.goalName, placeholder: '例如：完成数据库期末复习' })
              .layoutWeight(1).height(42).backgroundColor(this.palette().surface).borderRadius(10)
              .onChange((value: string) => this.goalName = value)
            Button('创建').height(42).enabled(!this.loading && this.goalName.trim().length > 0).onClick(() => this.createGoal())
          }.width('100%')

          Text('选择目标与每日时间').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
          if (this.goals.length === 0) {
            Text('请先创建一个学习目标').fontColor(this.palette().muted).fontSize(12)
          } else {
            Row({ space: 8 }) {
              ForEach(this.goals, (goal: StudentGoal) => {
                Text(goal.name).fontSize(11)
                  .fontColor(this.selectedGoalId === goal.goal_id ? '#FFFFFF' : this.palette().muted)
                  .backgroundColor(this.selectedGoalId === goal.goal_id ? this.palette().primary : this.palette().surface)
                  .borderRadius(10).padding({ left: 9, right: 9, top: 6, bottom: 6 })
                  .onClick(() => { this.selectedGoalId = goal.goal_id; this.planId = ''; this.summary = null; this.reload(); })
              }, (goal: StudentGoal) => goal.goal_id)
            }.width('100%')
          }
          Row({ space: 8 }) {
            TextInput({ text: this.minutesText, placeholder: '60' }).layoutWeight(1).height(42)
              .backgroundColor(this.palette().surface).borderRadius(10)
              .onChange((value: string) => this.minutesText = value)
            Button(this.loading ? '处理中…' : '生成计划草案').layoutWeight(2).height(42)
              .backgroundColor(this.palette().primary).fontColor('#FFFFFF')
              .enabled(!this.loading && this.selectedGoalId.length > 0)
              .onClick(() => this.generatePlan())
          }.width('100%')

          this.SummaryCard()
          if (this.planId.length > 0) {
            Row({ space: 8 }) {
              if (this.summary !== null && this.summary.stage === 'AWAITING_CONFIRMATION') {
                Button('确认计划').layoutWeight(1).height(38).onClick(() => this.decidePlan('ACCEPT'))
              }
              if (this.summary !== null && this.summary.stage === 'READY_TO_EXECUTE') {
                Button('创建个人待办').layoutWeight(1).height(38).onClick(() => this.executePlan())
              }
              if (this.summary !== null && ['IN_PROGRESS', 'STALE', 'EXPIRED'].indexOf(this.summary.stage) >= 0) {
                Button('重新规划').layoutWeight(1).height(38).onClick(() => this.replan())
              }
            }.width('100%')
          }
          Text('执行记录').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
          if (this.jobs.length === 0) Text('还没有目标执行记录').fontColor(this.palette().muted).fontSize(12)
          ForEach(this.jobs.slice(0, 8), (job: AgentJob) => this.RunCard(job), (job: AgentJob) => job.job_id)
        }.width('100%').padding({ left: 16, right: 16, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
