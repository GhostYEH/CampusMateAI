import { AgentRuntimeRepository } from '../../repository/AgentRuntimeRepository';
import {
  FinalReviewPlanVersion, FinalReviewDailyAgenda, FinalReviewDailyItem,
  FinalReviewAdjustmentProposal, AdjustmentProposalStatus,
  AgentApproval, AgentEvent
} from '../../data/AgentRuntimeModels';
import { AgentRunView, AgentEventReducer, IdempotencyKey } from '../../service/AgentEventReducer';
import { AgentRunPanel } from '../agent/AgentRunPanel';
import { ApprovalSheet } from '../agent/ApprovalSheet';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SseEvent } from '../../data/ApiClient';

// 期末复习计划页：展示计划版本与今日 agenda，提交完成证据与每日 check-in，
// 触发调整分析并审批 adjustment proposal。运行进度通过 SSE 实时归约。
@Component
export struct FinalReviewPlanPage {
  @Prop campaignId: string = '';
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  repository: AgentRuntimeRepository | null = null;
  onBack: () => void = () => {};
  @State planVersions: FinalReviewPlanVersion[] = [];
  @State todayAgenda: FinalReviewDailyAgenda | null = null;
  @State proposals: FinalReviewAdjustmentProposal[] = [];
  @State runView: AgentRunView | null = null;
  @State activeRunId: string = '';
  @State pendingApproval: AgentApproval | null = null;
  @State approvalSubmitting: boolean = false;
  @State loading: boolean = false;
  @State error: string = '';
  @State checkInDifficulty: string = '适中';
  @State checkInFeedback: string = '';
  @State active: boolean = true;
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  async aboutToAppear(): Promise<void> {
    await this.refreshAll();
  }

  aboutToDisappear(): void {
    this.active = false;
  }

  async refreshAll(): Promise<void> {
    if (this.repository === null || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      const versionsPromise: Promise<FinalReviewPlanVersion[]> = this.repository.listPlanVersions(this.campaignId);
      const agendaPromise: Promise<FinalReviewDailyAgenda> = this.repository.getTodayAgenda(this.campaignId);
      const proposalsPromise: Promise<FinalReviewAdjustmentProposal[]> =
        this.repository.listAdjustmentProposals(this.campaignId);
      this.planVersions = await versionsPromise;
      this.todayAgenda = await agendaPromise;
      this.proposals = await proposalsPromise;
    } catch (_) {
      this.error = '加载计划失败，请重试';
    } finally {
      this.loading = false;
    }
  }

  async generatePlan(): Promise<void> {
    if (this.repository === null) return;
    this.error = '';
    try {
      const run = await this.repository.generatePlan(this.campaignId);
      this.activeRunId = run.run_id;
      this.runView = AgentEventReducer.initial(run.run_id);
      this.subscribeRun(run.run_id);
    } catch (_) {
      this.error = '生成计划失败，请重试';
    }
  }

  async analyzeAdjustment(): Promise<void> {
    if (this.repository === null) return;
    this.error = '';
    try {
      const run = await this.repository.analyzeAdjustment(this.campaignId);
      this.activeRunId = run.run_id;
      this.runView = AgentEventReducer.initial(run.run_id);
      this.subscribeRun(run.run_id);
    } catch (_) {
      this.error = '分析调整失败，请重试';
    }
  }

  subscribeRun(runId: string): void {
    if (this.repository === null) return;
    const lastEventId: string = this.runView?.lastEventId ?? '';
    this.repository.streamEvents(runId, lastEventId, (event: SseEvent) => {
      if (!this.active) return;
      try {
        const raw: Record<string, Object> = JSON.parse(event.data) as Record<string, Object>;
        if (event.id !== undefined && event.id.length > 0) raw.id = event.id;
        if (event.event.length > 0) raw.type = event.event;
        const parsed: AgentEvent = AgentEventReducer.parseEvent(raw);
        this.runView = AgentEventReducer.append(this.runView ?? AgentEventReducer.initial(runId), parsed);
        if (parsed.approval_id !== null && parsed.approval_id.length > 0) {
          this.loadApproval(parsed.approval_id);
        }
      } catch (_) { /* 忽略无法解析的事件，不崩溃 */ }
    }).then(() => {
      if (this.active) this.refreshAll();
    }).catch(() => {
      if (this.active) this.error = '事件流中断，可刷新重试';
    });
  }

  async loadApproval(approvalId: string): Promise<void> {
    if (this.repository === null) return;
    try {
      this.pendingApproval = await this.repository.getApproval(approvalId);
    } catch (_) { /* 审批加载失败保持等待 */ }
  }

  async completeItem(itemId: string): Promise<void> {
    if (this.repository === null) return;
    try {
      await this.repository.completeDailyItem(itemId);
      await this.refreshAll();
    } catch (_) {
      this.error = '更新完成状态失败';
    }
  }

  async submitCheckIn(): Promise<void> {
    if (this.repository === null || this.todayAgenda === null) return;
    try {
      const completedIds: string[] = this.todayAgenda.items
        .filter((item: FinalReviewDailyItem) => item.completed)
        .map((item: FinalReviewDailyItem) => item.item_id);
      await this.repository.dailyCheckIn(
        this.campaignId, this.todayAgenda.date, completedIds,
        this.checkInDifficulty, this.checkInFeedback);
      this.checkInFeedback = '';
      this.error = '';
    } catch (_) {
      this.error = '提交 check-in 失败';
    }
  }

  async resolveProposal(proposalId: string, decision: string): Promise<void> {
    if (this.repository === null) return;
    this.approvalSubmitting = true;
    try {
      await this.repository.resolveAdjustment(proposalId, decision, '用户在期末复习页确认');
      await this.refreshAll();
    } catch (_) {
      this.error = '审批失败，请重试';
    } finally {
      this.approvalSubmitting = false;
    }
  }

  async resolveApproval(decision: string): Promise<void> {
    if (this.repository === null || this.pendingApproval === null) return;
    this.approvalSubmitting = true;
    try {
      const approval: AgentApproval = await this.repository.resolveApproval(
        this.pendingApproval.approval_id, decision, '用户确认',
        IdempotencyKey.forApprovalDecision(this.pendingApproval.approval_id, decision));
      this.runView = AgentEventReducer.applyApproval(this.runView ?? AgentEventReducer.initial(this.activeRunId), approval);
      this.pendingApproval = null;
      await this.refreshAll();
    } catch (_) {
      this.error = '审批失败，请重试';
    } finally {
      this.approvalSubmitting = false;
    }
  }

  proposalStatusLabel(status: AdjustmentProposalStatus): string {
    switch (status) {
      case AdjustmentProposalStatus.PROPOSED: return '待确认';
      case AdjustmentProposalStatus.APPROVED: return '已批准';
      case AdjustmentProposalStatus.REJECTED: return '已拒绝';
      case AdjustmentProposalStatus.EXPIRED: return '已过期';
      default: return '未知';
    }
  }

  build() {
    Column() {
      SecondaryHeader({ title: '复习计划', subtitle: `计划 ${this.campaignId.substring(0, 10)}`, darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 14 }) {
          if (this.error.length > 0) {
            Text(this.error).fontColor(this.palette().danger).fontSize(12)
          }

          AgentRunPanel({
            view: this.runView,
            darkMode: this.darkMode,
            reduceMotion: this.reduceMotion,
            onOpenArtifact: (_: string) => {},
            onCancel: () => { if (this.repository !== null && this.activeRunId.length > 0) this.repository.cancelRun(this.activeRunId, `fr:cancel:${this.activeRunId}`); }
          })

          if (this.planVersions.length === 0) {
            Column({ space: 8 }) {
              Text('尚未生成计划').fontColor(this.palette().text).fontSize(14)
              Button('生成计划提案').width('100%').height(44)
                .backgroundColor(this.palette().primary).fontColor('#FFFFFF').borderRadius(14)
                .onClick(() => this.generatePlan())
            }.width('100%').padding(16)
          } else {
            Text('计划版本').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Medium)
            ForEach(this.planVersions, (version: FinalReviewPlanVersion) => {
              Column({ space: 4 }) {
                Row() {
                  Text(`v${version.version}`).fontColor(this.palette().primary).fontSize(14).fontWeight(FontWeight.Bold)
                  Text(version.status).fontColor(this.palette().muted).fontSize(11).margin({ left: 8 })
                  Blank()
                  Text(`${version.daily_items.length} 项`).fontColor(this.palette().muted).fontSize(11)
                }.width('100%')
                Text(version.summary).fontColor(this.palette().text).fontSize(12).lineHeight(18)
              }.width('100%').padding(12)
              .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(14)
            }, (version: FinalReviewPlanVersion) => `${version.version}`)
          }

          if (this.todayAgenda !== null) {
            Text('今日安排').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Medium)
            if (this.todayAgenda.items.length === 0) {
              Text('今日暂无任务').fontColor(this.palette().muted).fontSize(12)
            } else {
              ForEach(this.todayAgenda.items, (item: FinalReviewDailyItem) => {
                Row({ space: 10 }) {
                  Checkbox().select(item.completed)
                    .onChange((value: boolean) => { if (value && !item.completed) this.completeItem(item.item_id); })
                  Column({ space: 2 }) {
                    Text(item.course_name).fontColor(this.palette().text).fontSize(13).maxLines(1)
                    Text(`${item.topic} · ${item.planned_minutes} 分钟`).fontColor(this.palette().muted).fontSize(11)
                  }.layoutWeight(1).alignItems(HorizontalAlign.Start)
                }.width('100%').padding(10)
                .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
              }, (item: FinalReviewDailyItem) => item.item_id)
            }

            Text('每日 check-in').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
            Row({ space: 10 }) {
              ForEach(['轻松', '适中', '紧张'], (level: string) => {
                Text(level).fontSize(12).layoutWeight(1).textAlign(TextAlign.Center)
                  .fontColor(this.checkInDifficulty === level ? '#FFFFFF' : this.palette().muted)
                  .backgroundColor(this.checkInDifficulty === level ? this.palette().primary : this.palette().surface)
                  .borderRadius(10).padding({ top: 6, bottom: 6 })
                  .onClick(() => this.checkInDifficulty = level)
              })
            }.width('100%')
            TextInput({ text: this.checkInFeedback, placeholder: '选填：今日反馈' })
              .width('100%').height(40).fontSize(13)
              .backgroundColor(this.palette().surface).borderRadius(10)
              .onChange((value: string) => this.checkInFeedback = value)
            Button('提交 check-in').width('100%').height(42)
              .backgroundColor(this.palette().surface).fontColor(this.palette().text)
              .border({ width: 1, color: this.palette().line }).borderRadius(12)
              .onClick(() => this.submitCheckIn())
          }

          Text('调整建议').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Medium)
          Button('触发调整分析').width('100%').height(42)
            .backgroundColor(this.palette().surface).fontColor(this.palette().primary)
            .border({ width: 1, color: this.palette().primary }).borderRadius(12)
            .onClick(() => this.analyzeAdjustment())
          ForEach(this.proposals, (proposal: FinalReviewAdjustmentProposal) => {
            Column({ space: 6 }) {
              Row() {
                Text(proposal.summary).fontColor(this.palette().text).fontSize(13).layoutWeight(1)
                Text(this.proposalStatusLabel(proposal.status)).fontColor(this.palette().primary).fontSize(11)
              }.width('100%')
              Text(proposal.rationale).fontColor(this.palette().muted).fontSize(11).lineHeight(16)
              if (proposal.status === AdjustmentProposalStatus.PROPOSED) {
                Row({ space: 10 }) {
                  Button('拒绝').layoutWeight(1).height(38)
                    .backgroundColor(this.palette().surface).fontColor(this.palette().text)
                    .border({ width: 1, color: this.palette().line }).borderRadius(10)
                    .onClick(() => this.resolveProposal(proposal.proposal_id, 'rejected'))
                  Button('批准').layoutWeight(1).height(38)
                    .backgroundColor(this.palette().primary).fontColor('#FFFFFF').borderRadius(10)
                    .onClick(() => this.resolveProposal(proposal.proposal_id, 'approved'))
                }.width('100%')
              }
            }.width('100%').padding(12)
            .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(14)
          }, (proposal: FinalReviewAdjustmentProposal) => proposal.proposal_id)
        }.width('100%').padding({ left: 16, right: 16, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)

      ApprovalSheet({
        approval: this.pendingApproval,
        darkMode: this.darkMode,
        submitting: this.approvalSubmitting,
        onApprove: () => this.resolveApproval('approved'),
        onReject: () => this.resolveApproval('rejected'),
        onDismiss: () => { this.pendingApproval = null; }
      })
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}