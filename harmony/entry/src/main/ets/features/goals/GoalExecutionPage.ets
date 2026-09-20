import { AgentRuntimeRepository } from '../../repository/AgentRuntimeRepository';
import {
  AgentJob, AgentRun, LearningPlanSummary, StudentGoal, RunStatus, AgentEnumParser,
  CandidateAnnotation, LearnerStateSnapshot, ForecastSummary, DataSourceControl,
  ModelTransparency, ModelCapabilityTransparency, AdaptiveInterventionOutcome
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
  // 世界模型只读视图：与 error 分开，取不到时只降级这一块，不影响目标/计划区域。
  @State snapshots: LearnerStateSnapshot[] = [];
  @State forecasts: ForecastSummary[] = [];
  @State dataControls: DataSourceControl[] = [];
  @State transparency: ModelTransparency | null = null;
  @State interventionOutcome: AdaptiveInterventionOutcome | null = null;
  @State worldModelDegraded: string = '';
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
    await this.reloadWorldModel();
  }

  /**
   * 加载世界模型只读视图。
   *
   * 任何一项失败都不影响其它区域：只把这一块标成"只读降级"，
   * 而不是把整页替换成错误。世界模型是只读增强项，不是页面成立的前提。
   */
  async reloadWorldModel(): Promise<void> {
    if (this.repository === null) return;
    let loaded: number = 0;
    try {
      const core: LearnerStateSnapshot[] = await this.repository.listLearnerStateSnapshots('CORE');
      const world: LearnerStateSnapshot[] = await this.repository.listLearnerStateSnapshots('WORLD');
      this.snapshots = core.concat(world);
      if (this.snapshots.length > 0) loaded = loaded + 1;
    } catch (_) { this.snapshots = []; }
    try {
      this.forecasts = await this.repository.listForecasts();
      if (this.forecasts.length > 0) loaded = loaded + 1;
    } catch (_) { this.forecasts = []; }
    try {
      this.dataControls = await this.repository.listDataSourceControls();
      if (this.dataControls.length > 0) loaded = loaded + 1;
    } catch (_) { this.dataControls = []; }
    try {
      this.transparency = await this.repository.getModelTransparency();
      loaded = loaded + 1;
    } catch (_) { this.transparency = null; }
    try {
      this.interventionOutcome = await this.repository.getInterventionOutcome();
    } catch (_) { this.interventionOutcome = null; }
    this.worldModelDegraded = loaded === 0 ? '世界模型暂时不可用，已降级为只读展示' : '';
  }

  async toggleDataSource(sourceKey: string, status: string): Promise<void> {
    if (this.repository === null) return;
    try {
      this.dataControls = await this.repository.setDataSourceStatus(sourceKey, status);
      this.worldModelDegraded = '';
    } catch (_) {
      this.worldModelDegraded = '数据源状态更新失败，已保持原状态';
    }
  }

  qualityLabel(quality: string): string {
    switch (quality) {
      case 'verified': return '已验证';
      case 'partial': return '部分可信';
      case 'stale': return '已过期';
      default: return '不可用';
    }
  }

  forecastLabel(forecastType: string): string {
    switch (forecastType) {
      case 'DEADLINE_COMPLETION_RISK': return '截止风险';
      case 'UPCOMING_WORKLOAD': return '未来负载';
      case 'SCHEDULE_CONFLICT_RISK': return '日程冲突';
      case 'GOAL_PROGRESS_OUTLOOK': return '目标进展';
      case 'ROUTINE_CONTINUITY': return '作息连续性';
      default: return forecastType;
    }
  }

  decisionLabel(decision: string | null): string {
    switch (decision) {
      case 'CONTINUE': return '继续当前计划';
      case 'WAIT_FOR_EVIDENCE': return '等待更多证据';
      case 'REPLAN': return '重新规划';
      case 'SUSPEND': return '暂停调整';
      default: return '尚未产生';
    }
  }

  decisionStatusLabel(status: string | null): string {
    switch (status) {
      case 'APPLIED': return '已应用';
      case 'PENDING': return '待处理';
      case 'APPLYING': return '处理中';
      case 'FAILED': return '处理失败';
      default: return '未处理';
    }
  }

  sourceLabel(sourceKey: string): string {
    switch (sourceKey) {
      case 'CORE_STUDY': return '核心学习记录';
      case 'PERSONAL_TASK': return '个人待办';
      case 'CHAOXING': return '学习通';
      case 'EDU': return '教务系统';
      case 'MODEL_SHADOW': return '模型影子评测';
      case 'PROACTIVE_SUGGESTIONS': return '主动建议';
      default: return sourceKey;
    }
  }

  candidateReasonLabel(reason: string | null): string {
    switch (reason) {
      case 'canary_feature_flag_disabled': return '金丝雀展示未开启';
      case 'candidate_model_not_configured': return '候选模型未配置';
      case 'model_shadow_paused_for_user': return '你已暂停模型影子评测';
      case 'no_promotion_decision': return '候选模型尚未通过评测';
      case 'quality_gates_failed': return '候选模型未通过质量门控';
      case 'circuit_breaker_open': return '候选模型暂时熔断';
      case 'MODEL_RATE_LIMITED': return '本次未命中采样';
      case 'MODEL_TIMEOUT': return '候选模型响应超时';
      case 'MODEL_SCHEMA_INVALID': return '候选模型输出格式不合法';
      case 'MODEL_POLICY_VIOLATION': return '候选模型输出违反安全策略';
      case 'MODEL_DISABLED': return '候选模型未启用';
      case 'MODEL_UNAVAILABLE': return '候选模型不可用';
      case 'candidate_invocation_failed': return '候选模型调用失败';
      case 'no_eligible_feature_input': return '当前计划没有可用的结构化特征';
      default: return reason === null ? '不可用' : reason;
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
        if (this.summary.warning_codes.length > 0) {
          Text(`数据质量警告：${this.summary.warning_codes.join('、')}`).fontColor(this.palette().muted).fontSize(11)
        }
        if (this.summary.candidate_annotation !== null) {
          this.CandidateRow(this.summary.candidate_annotation)
        }
        ForEach(this.summary.recommendations, (item: string) => {
          Text(`• ${item}`).fontColor(this.palette().muted).fontSize(11)
        }, (item: string) => item)
      }.width('100%').padding(12)
        .backgroundColor(this.palette().glass.surface)
        .border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
    }
  }

  /** 候选模型只读注解：可识别、可降级、可追溯；绝不与确定性结果混为一谈。 */
  @Builder CandidateRow(annotation: CandidateAnnotation) {
    Column({ space: 4 }) {
      Text(annotation.available ? '候选模型建议（只读）' : '候选模型建议不可用')
        .fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Medium)
      if (annotation.available) {
        if (annotation.summary !== null) {
          Text(annotation.summary).fontColor(this.palette().text).fontSize(12)
        }
        if (annotation.claim_codes.length > 0) {
          Text(`依据：${annotation.claim_codes.join('、')}`).fontColor(this.palette().muted).fontSize(11)
        }
        Text(`来源：${annotation.model_key === null ? '未知' : annotation.model_key} · 提示版本 ${annotation.prompt_version === null ? '未知' : annotation.prompt_version}`)
          .fontColor(this.palette().muted).fontSize(10)
      } else {
        Text(`已回退到确定性结果：${this.candidateReasonLabel(annotation.reason)}`)
          .fontColor(this.palette().muted).fontSize(11)
      }
      Text('这是候选模型的只读展示，不会修改你的状态、计划或待办。')
        .fontColor(this.palette().muted).fontSize(10)
    }.width('100%').padding(10)
      .backgroundColor(this.palette().surface)
      .border({ width: 1, color: this.palette().glass.border, style: BorderStyle.Dashed }).borderRadius(10)
  }

  @Builder WorldModelCard() {
    Column({ space: 6 }) {
      Text('学生世界模型（只读）').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
      if (this.worldModelDegraded.length > 0) {
        Text(`只读降级：${this.worldModelDegraded}`).fontColor(this.palette().muted).fontSize(11)
      }

      Text('状态摘要').fontColor(this.palette().text).fontSize(12)
      if (this.snapshots.length === 0) {
        Text('暂无状态快照（可能是还没有可投影的学习记录）').fontColor(this.palette().muted).fontSize(11)
      } else {
        ForEach(this.snapshots.slice(0, 6), (item: LearnerStateSnapshot) => {
          Column({ space: 2 }) {
            Text(`${item.projection_kind} · ${item.state_type} · 质量 ${this.qualityLabel(item.data_quality)} · 置信度 ${item.confidence.toFixed(2)}`)
              .fontColor(this.palette().text).fontSize(11)
            if (item.warning_codes.length > 0) {
              Text(`警告：${item.warning_codes.join('、')}`).fontColor(this.palette().muted).fontSize(10)
            }
          }.width('100%')
        }, (item: LearnerStateSnapshot) => item.snapshot_id)
      }

      Text('风险预测').fontColor(this.palette().text).fontSize(12)
      if (this.forecasts.length === 0) {
        Text('暂无预测结果').fontColor(this.palette().muted).fontSize(11)
      } else {
        ForEach(this.forecasts.slice(0, 5), (item: ForecastSummary) => {
          Column({ space: 2 }) {
            Text(`${this.forecastLabel(item.forecast_type)} · ${item.probability === null ? '无概率' : `${Math.round(item.probability * 100)}%`} · 质量 ${this.qualityLabel(item.data_quality)}`)
              .fontColor(this.palette().text).fontSize(11)
            if (item.limitations.length > 0) {
              Text(`限制：${item.limitations.join('、')}`).fontColor(this.palette().muted).fontSize(10)
            }
          }.width('100%')
        }, (item: ForecastSummary) => item.forecast_id)
      }

      Text('计划与自动重规划').fontColor(this.palette().text).fontSize(12)
      if (this.interventionOutcome === null) {
        Text('确认计划后，系统会在观测窗结束后自动核对执行情况；只有证据支持时才会调整计划。')
          .fontColor(this.palette().muted).fontSize(11)
      } else {
        Text(this.interventionOutcome.decision_status === 'APPLIED'
          ? `系统决定：${this.decisionLabel(this.interventionOutcome.decision)}（已调整学习计划）`
          : `系统决定：${this.decisionLabel(this.interventionOutcome.decision)}（${this.decisionStatusLabel(this.interventionOutcome.decision_status)}）`)
          .fontColor(this.palette().text).fontSize(11)
        // 归因范围：无目标计划同样观测、同样会安全替换计划，必须写明，避免误读成"不会跟进"。
        Text(this.interventionOutcome.scope_type === 'PLAN'
          ? '归因范围：计划本身（未绑定学习目标）——系统按计划范围观测与评估，有证据时同样会安全替换计划。'
          : '归因范围：学习目标——系统按目标范围观测与评估。')
          .fontColor(this.palette().muted).fontSize(10)
        Text(`观测：${this.interventionOutcome.observed_outcome} · 执行信号 ${this.interventionOutcome.execution_signal} · 归因 ${this.interventionOutcome.causal_claim}`)
          .fontColor(this.palette().muted).fontSize(10)
        if (this.interventionOutcome.decision_reason_codes.length > 0) {
          Text(`原因码：${this.interventionOutcome.decision_reason_codes.join('、')}`).fontColor(this.palette().muted).fontSize(10)
        }
      }

      Text('反事实模拟').fontColor(this.palette().text).fontSize(12)
      Text('本端暂未提供反事实模拟入口；模拟是纯只读推演，不会执行干预。如需运行请在 Web 端「学习预测」页操作。')
        .fontColor(this.palette().muted).fontSize(11)

      Text('数据源控制').fontColor(this.palette().text).fontSize(12)
      if (this.dataControls.length === 0) {
        Text('暂无可控制的数据源').fontColor(this.palette().muted).fontSize(11)
      } else {
        ForEach(this.dataControls, (item: DataSourceControl) => {
          Row() {
            Text(`${this.sourceLabel(item.source_key)} · ${item.status === 'ENABLED' ? '已启用' : '已暂停'}`)
              .fontColor(this.palette().text).fontSize(11).layoutWeight(1)
            if (item.status === 'ENABLED' && item.can_pause) {
              Button('暂停').height(28).fontSize(11)
                .onClick(() => this.toggleDataSource(item.source_key, 'PAUSED'))
            } else if (item.can_resume) {
              Button('恢复').height(28).fontSize(11)
                .onClick(() => this.toggleDataSource(item.source_key, 'ENABLED'))
            }
          }.width('100%')
        }, (item: DataSourceControl) => item.source_key)
      }

      Text('模型透明度').fontColor(this.palette().text).fontSize(12)
      if (this.transparency === null) {
        Text('暂无模型透明度数据').fontColor(this.palette().muted).fontSize(11)
      } else {
        Text(`CampusMate-LM 影响正式状态：${this.transparency.campusmate_lm_affects_production ? '是' : '否'}`)
          .fontColor(this.palette().muted).fontSize(11)
        Text(`影子结果会修改计划：${this.transparency.shadow_results_modify_plans ? '是' : '否'}`)
          .fontColor(this.palette().muted).fontSize(11)
        Text(`已观测到真实模型推理：${this.transparency.real_inference_observed ? '是' : '否（当前为固定预测文件）'}`)
          .fontColor(this.palette().muted).fontSize(11)
        ForEach(this.transparency.capabilities, (item: ModelCapabilityTransparency) => {
          Text(`${item.capability_name} · ${item.campusmate_lm_status} · 质量门控${item.quality_gate_passed ? '通过' : '未通过'}`)
            .fontColor(this.palette().muted).fontSize(10)
        }, (item: ModelCapabilityTransparency) => item.capability_name)
      }
    }.width('100%').padding(12)
      .backgroundColor(this.palette().glass.surface)
      .border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
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
          this.WorldModelCard()
          Text('执行记录').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
          if (this.jobs.length === 0) Text('还没有目标执行记录').fontColor(this.palette().muted).fontSize(12)
          ForEach(this.jobs.slice(0, 8), (job: AgentJob) => this.RunCard(job), (job: AgentJob) => job.job_id)
        }.width('100%').padding({ left: 16, right: 16, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
