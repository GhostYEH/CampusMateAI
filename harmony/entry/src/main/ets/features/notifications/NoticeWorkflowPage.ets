import { AgentRuntimeRepository } from '../../repository/AgentRuntimeRepository';
import {
  NoticeWorkflow, NoticeWorkflowAction, NoticeWorkflowStatus,
  NoticeActionStatus, RiskLevel, AgentApproval
} from '../../data/AgentRuntimeModels';
import { AgentEventReducer } from '../../service/AgentEventReducer';
import { ApprovalSheet } from '../agent/ApprovalSheet';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

// 通知事务页：粘贴通知先 /notices/manual 再创建 workflow，展示 uncertainty、
// risk、action 状态、审批与材料清单。MANUAL_ONLY/外部动作不自动执行。
// 设备通知订阅权限与服务端 source 权限分开，仅展示准确能力说明。
@Component
export struct NoticeWorkflowPage {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop deviceNotificationCapabilityLabel: string = '设备通知订阅权限需在系统设置中授权';
  repository: AgentRuntimeRepository | null = null;
  onBack: () => void = () => {};
  @State noticeText: string = '';
  @State workflow: NoticeWorkflow | null = null;
  @State submitting: boolean = false;
  @State actionSubmitting: string = '';
  @State error: string = '';
  @State pendingApproval: AgentApproval | null = null;
  @State approvalSubmitting: boolean = false;
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  async submitNotice(): Promise<void> {
    if (this.repository === null || this.noticeText.trim().length === 0 || this.submitting) return;
    this.submitting = true;
    this.error = '';
    try {
      const noticeId: string = await this.repository.createManualNotice(this.noticeText.trim());
      if (noticeId.length === 0) {
        this.error = '创建通知失败，未返回通知 ID';
        return;
      }
      const workflow: NoticeWorkflow = await this.repository.createNoticeWorkflow(
        noticeId, this.noticeText.trim(), 'manual_input');
      this.workflow = workflow;
      this.noticeText = '';
    } catch (_) {
      this.error = '处理通知失败，请重试';
    } finally {
      this.submitting = false;
    }
  }

  async resolveAction(actionId: string, decision: string): Promise<void> {
    if (this.repository === null) return;
    this.actionSubmitting = actionId;
    this.error = '';
    try {
      await this.repository.resolveNoticeAction(actionId, decision);
      if (this.workflow !== null) {
        this.workflow = await this.repository.getNoticeWorkflow(this.workflow.workflow_id);
      }
    } catch (_) {
      this.error = '操作失败，请重试';
    } finally {
      this.actionSubmitting = '';
    }
  }

  async executeAction(actionId: string): Promise<void> {
    if (this.repository === null) return;
    this.actionSubmitting = actionId;
    this.error = '';
    try {
      await this.repository.executeNoticeAction(actionId);
      if (this.workflow !== null) {
        this.workflow = await this.repository.getNoticeWorkflow(this.workflow.workflow_id);
      }
    } catch (_) {
      this.error = '执行失败，请重试';
    } finally {
      this.actionSubmitting = '';
    }
  }

  workflowStatusLabel(status: NoticeWorkflowStatus): string {
    switch (status) {
      case NoticeWorkflowStatus.CREATED: return '已创建';
      case NoticeWorkflowStatus.ANALYZING: return '分析中';
      case NoticeWorkflowStatus.WAITING_CONFIRMATION: return '待确认';
      case NoticeWorkflowStatus.PROCESSING: return '处理中';
      case NoticeWorkflowStatus.COMPLETED: return '已完成';
      case NoticeWorkflowStatus.EXPIRED: return '已过期';
      case NoticeWorkflowStatus.FAILED: return '失败';
      default: return '未知';
    }
  }

  actionStatusLabel(status: NoticeActionStatus): string {
    switch (status) {
      case NoticeActionStatus.PROPOSED: return '待确认';
      case NoticeActionStatus.APPROVED: return '已批准';
      case NoticeActionStatus.EXECUTING: return '执行中';
      case NoticeActionStatus.DONE: return '已完成';
      case NoticeActionStatus.REJECTED: return '已拒绝';
      case NoticeActionStatus.FAILED: return '失败';
      case NoticeActionStatus.EXPIRED: return '已过期';
      default: return '未知';
    }
  }

  riskLabel(risk: RiskLevel): string {
    switch (risk) {
      case RiskLevel.AUTO_SAFE: return '自动安全';
      case RiskLevel.CONFIRM_REQUIRED: return '需确认';
      case RiskLevel.MANUAL_ONLY: return '需手动';
      default: return '风险未知';
    }
  }

  build() {
    Column() {
      SecondaryHeader({ title: '通知事务', subtitle: '把通知变成可追踪的待办', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 14 }) {
          if (this.error.length > 0) {
            Text(this.error).fontColor(this.palette().danger).fontSize(12)
          }

          Text('粘贴通知内容').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
          TextArea({ text: this.noticeText, placeholder: '粘贴校园通知、学习通提醒或教务通知全文' })
            .width('100%').height(100).fontSize(13)
            .backgroundColor(this.palette().surface).borderRadius(12)
            .onChange((value: string) => this.noticeText = value)
          Button(this.submitting ? '处理中…' : '生成事务流程')
            .width('100%').height(46)
            .backgroundColor(this.palette().primary).fontColor('#FFFFFF').borderRadius(14)
            .enabled(!this.submitting && this.noticeText.trim().length > 0)
            .onClick(() => this.submitNotice())

          if (this.workflow !== null) {
            Row({ space: 10 }) {
              Text('流程状态').fontColor(this.palette().muted).fontSize(11)
              Text(this.workflowStatusLabel(this.workflow.status)).fontColor(this.palette().primary).fontSize(12)
            }.width('100%')

            if (this.workflow.uncertainty.missing_fields.length > 0 ||
                this.workflow.uncertainty.notes.length > 0) {
              Column({ space: 4 }) {
                Text('不确定性').fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Medium)
                if (this.workflow.uncertainty.missing_fields.length > 0) {
                  Text(`缺失字段：${this.workflow.uncertainty.missing_fields.join('、')}`)
                    .fontColor('#f59e0b').fontSize(11)
                }
                if (this.workflow.uncertainty.notes.length > 0) {
                  Text(this.workflow.uncertainty.notes).fontColor(this.palette().muted).fontSize(11).lineHeight(16)
                }
              }.width('100%').padding(10)
              .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
            }

            Text('动作清单').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
            ForEach(this.workflow.actions, (action: NoticeWorkflowAction) => {
              Column({ space: 6 }) {
                Row() {
                  Text(action.title).fontColor(this.palette().text).fontSize(13).layoutWeight(1)
                  Text(this.riskLabel(action.risk_level))
                    .fontSize(10).fontColor('#FFFFFF')
                    .backgroundColor(action.risk_level === RiskLevel.MANUAL_ONLY ? this.palette().danger : this.palette().primary)
                    .borderRadius(8).padding({ left: 6, right: 6, top: 2, bottom: 2 })
                }.width('100%')
                Row() {
                  Text(this.actionStatusLabel(action.status)).fontColor(this.palette().muted).fontSize(11)
                  if (action.is_external) {
                    Text('外部动作').fontColor(this.palette().danger).fontSize(10).margin({ left: 8 })
                  }
                }.width('100%')
                if (action.materials.length > 0) {
                  Text(`材料：${action.materials.join('、')}`).fontColor(this.palette().muted).fontSize(11).lineHeight(16)
                }
                if (action.status === NoticeActionStatus.PROPOSED) {
                  Row({ space: 8 }) {
                    Button('拒绝').layoutWeight(1).height(36)
                      .backgroundColor(this.palette().surface).fontColor(this.palette().text)
                      .border({ width: 1, color: this.palette().line }).borderRadius(10)
                      .enabled(this.actionSubmitting.length === 0)
                      .onClick(() => this.resolveAction(action.action_id, 'rejected'))
                    if (AgentEventReducer.isManualOnly(action.risk_level) || action.is_external) {
                      Button('我已手动完成').layoutWeight(1).height(36)
                        .backgroundColor(this.palette().surface).fontColor(this.palette().primary)
                        .border({ width: 1, color: this.palette().primary }).borderRadius(10)
                        .enabled(this.actionSubmitting.length === 0)
                        .onClick(() => this.resolveAction(action.action_id, 'approved'))
                    } else {
                      Button('确认执行').layoutWeight(1).height(36)
                        .backgroundColor(this.palette().primary).fontColor('#FFFFFF').borderRadius(10)
                        .enabled(this.actionSubmitting.length === 0)
                        .onClick(() => this.executeAction(action.action_id))
                    }
                  }.width('100%')
                }
              }.width('100%').padding(12)
              .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(14)
            }, (action: NoticeWorkflowAction) => action.action_id)
          }

          Column({ space: 4 }) {
            Text('权限说明').fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Medium)
            Text(this.deviceNotificationCapabilityLabel).fontColor(this.palette().muted).fontSize(11).lineHeight(16)
            Text('服务端 source 权限控制哪些来源可自动处理；设备通知订阅权限是本机系统设置，两者相互独立。')
              .fontColor(this.palette().muted).fontSize(11).lineHeight(16)
          }.width('100%').padding(12)
          .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(14)
        }.width('100%').padding({ left: 16, right: 16, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)

      ApprovalSheet({
        approval: this.pendingApproval,
        darkMode: this.darkMode,
        submitting: this.approvalSubmitting,
        onApprove: () => { this.pendingApproval = null; },
        onReject: () => { this.pendingApproval = null; },
        onDismiss: () => { this.pendingApproval = null; }
      })
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}