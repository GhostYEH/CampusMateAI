import {
  AgentApproval,
  ApprovalStatus,
  RiskLevel
} from '../../data/AgentRuntimeModels';
import { AgentEventReducer } from '../../service/AgentEventReducer';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

// 底部审批确认面。MANUAL_ONLY 动作不提供"自动执行"，仅确认用户将手动完成；
// EXPIRED/UNKNOWN 保持等待，允许刷新或返回，不自动放行。
@Component
export struct ApprovalSheet {
  @Prop approval: AgentApproval | null = null;
  @Prop darkMode: boolean = false;
  @Prop submitting: boolean = false;
  onApprove: () => void = () => {};
  onReject: () => void = () => {};
  onDismiss: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  riskLabel(risk: RiskLevel): string {
    switch (risk) {
      case RiskLevel.AUTO_SAFE: return '自动安全';
      case RiskLevel.CONFIRM_REQUIRED: return '需要确认';
      case RiskLevel.MANUAL_ONLY: return '需手动完成';
      default: return '风险未知';
    }
  }

  isManualOnly(): boolean {
    return this.approval !== null && AgentEventReducer.isManualOnly(this.approval.risk_level);
  }

  isExpired(): boolean {
    return this.approval !== null &&
      (this.approval.status === ApprovalStatus.EXPIRED || this.approval.status === ApprovalStatus.UNKNOWN);
  }

  build() {
    if (this.approval === null) {
      Column() {}
    } else {
      Column() {
        Column({ space: 14 }) {
          Row() {
            Text('待确认动作').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold).layoutWeight(1)
            SymbolGlyph($r('sys.symbol.xmark')).fontSize(18).fontColor([this.palette().muted])
              .onClick(() => this.onDismiss())
          }.width('100%')

          Text(this.approval.action_summary).fontColor(this.palette().text).fontSize(15).lineHeight(22)

          Row({ space: 8 }) {
            Text(this.riskLabel(this.approval.risk_level))
              .fontSize(12).fontColor('#FFFFFF')
              .backgroundColor(this.isManualOnly() ? this.palette().danger : this.palette().primary)
              .borderRadius(10).padding({ left: 10, right: 10, top: 4, bottom: 4 })
            if (this.isExpired()) {
              Text('已过期或状态未知，请刷新').fontSize(12).fontColor(this.palette().danger)
            }
          }

          if (this.isManualOnly()) {
            Column({ space: 8 }) {
              Text('该动作涉及外部系统提交，CampusMate 不会代你执行。请在对应平台手动完成后，回到这里标记结果。')
                .fontColor(this.palette().muted).fontSize(12).lineHeight(18)
              Button('我已知晓，去手动完成')
                .width('100%').height(46)
                .backgroundColor(this.palette().surface).fontColor(this.palette().text)
                .border({ width: 1, color: this.palette().line }).borderRadius(14)
                .onClick(() => this.onDismiss())
            }.width('100%')
          } else if (this.isExpired()) {
            Button('刷新审批状态')
              .width('100%').height(46)
              .backgroundColor(this.palette().surface).fontColor(this.palette().text)
              .border({ width: 1, color: this.palette().line }).borderRadius(14)
              .onClick(() => this.onDismiss())
          } else {
            Row({ space: 12 }) {
              Button('拒绝')
                .layoutWeight(1).height(46)
                .backgroundColor(this.palette().surface).fontColor(this.palette().text)
                .border({ width: 1, color: this.palette().line }).borderRadius(14)
                .enabled(!this.submitting)
                .onClick(() => this.onReject())
              Button('确认执行')
                .layoutWeight(1).height(46)
                .backgroundColor(this.palette().primary).fontColor('#FFFFFF').borderRadius(14)
                .enabled(!this.submitting)
                .onClick(() => this.onApprove())
            }.width('100%')
          }
        }.width('100%').padding(20)
        .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
        .border({ width: 1, color: this.palette().glass.border }).borderRadius(20)
      }.width('100%').padding({ left: 16, right: 16, bottom: 20 })
    }
  }
}