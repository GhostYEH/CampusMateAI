import { AgentRunView } from '../../service/AgentEventReducer';
import {
  RunStatus, RunPhase, AgentEventType, AgentEvent
} from '../../data/AgentRuntimeModels';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

// 统一 Agent 运行面板：展示状态、阶段、进度、事件流和产物入口。
// 不渲染模型 prompt 或隐藏推理，只展示 summary 与安全状态。
@Component
export struct AgentRunPanel {
  @Prop view: AgentRunView | null = null;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  onOpenArtifact: (artifactId: string) => void = (_: string) => {};
  onCancel: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  statusLabel(status: RunStatus): string {
    switch (status) {
      case RunStatus.QUEUED: return '已入队';
      case RunStatus.RUNNING: return '运行中';
      case RunStatus.AWAITING_APPROVAL: return '等待确认';
      case RunStatus.SUCCEEDED: return '已完成';
      case RunStatus.PARTIAL: return '部分完成';
      case RunStatus.FAILED: return '已失败';
      case RunStatus.CANCELLED: return '已取消';
      default: return '状态未知';
    }
  }

  statusColor(status: RunStatus): string {
    switch (status) {
      case RunStatus.SUCCEEDED: return this.palette().primary;
      case RunStatus.PARTIAL: return '#f59e0b';
      case RunStatus.FAILED: return this.palette().danger;
      case RunStatus.CANCELLED: return this.palette().muted;
      case RunStatus.AWAITING_APPROVAL: return '#f59e0b';
      default: return this.palette().muted;
    }
  }

  phaseLabel(phase: RunPhase): string {
    switch (phase) {
      case RunPhase.CONTEXT_BUILDING: return '构建上下文';
      case RunPhase.WAITING_FOR_MODEL: return '模型推理中';
      case RunPhase.VALIDATING_OUTPUT: return '校验输出';
      case RunPhase.WAITING_FOR_TOOL: return '执行工具';
      case RunPhase.WAITING_FOR_APPROVAL: return '等待审批';
      case RunPhase.PERSISTING_RESULT: return '保存结果';
      case RunPhase.RECOVERY_CHECKING: return '恢复检查';
      case RunPhase.IDLE: return '空闲';
      default: return '阶段未知';
    }
  }

  eventLabel(type: AgentEventType): string {
    switch (type) {
      case AgentEventType.RUN_QUEUED: return '入队';
      case AgentEventType.RUN_STARTED: return '开始';
      case AgentEventType.CONTEXT_READY: return '上下文就绪';
      case AgentEventType.MODEL_STARTED: return '模型启动';
      case AgentEventType.MODEL_COMPLETED: return '模型完成';
      case AgentEventType.MODEL_FALLBACK: return '模型降级';
      case AgentEventType.TOOL_STARTED: return '工具启动';
      case AgentEventType.TOOL_COMPLETED: return '工具完成';
      case AgentEventType.TOOL_FAILED: return '工具失败';
      case AgentEventType.APPROVAL_REQUIRED: return '需要确认';
      case AgentEventType.APPROVAL_RESOLVED: return '确认已处理';
      case AgentEventType.ARTIFACT_CREATED: return '产物已生成';
      case AgentEventType.RUN_PARTIAL: return '部分完成';
      case AgentEventType.RUN_COMPLETED: return '完成';
      case AgentEventType.RUN_FAILED: return '失败';
      case AgentEventType.RUN_CANCELLED: return '取消';
      default: return '事件';
    }
  }

  build() {
    if (this.view === null) {
      Column({ space: 10 }) {
        SymbolGlyph($r('sys.symbol.sparkles')).fontSize(34).fontColor([this.palette().muted])
        Text('暂无运行').fontColor(this.palette().muted).fontSize(13)
      }.width('100%').padding(30)
    } else {
      Column({ space: 14 }) {
        Row({ space: 10 }) {
          Text(this.statusLabel(this.view.status))
            .fontSize(13).fontColor('#FFFFFF')
            .backgroundColor(this.statusColor(this.view.status))
            .borderRadius(10).padding({ left: 10, right: 10, top: 4, bottom: 4 })
          Text(this.phaseLabel(this.view.phase)).fontColor(this.palette().muted).fontSize(12)
          Blank()
          if (this.view.status === RunStatus.RUNNING || this.view.status === RunStatus.AWAITING_APPROVAL) {
            Text('取消').fontColor(this.palette().danger).fontSize(12).onClick(() => this.onCancel())
          }
        }.width('100%')

        if (this.view.progress !== null) {
          Column({ space: 6 }) {
            Row() {
              Text(`进度 ${this.view.progress.current}/${this.view.progress.total}`)
                .fontColor(this.palette().text).fontSize(12).layoutWeight(1)
              Text(`${this.view.progress.percent}%`).fontColor(this.palette().primary).fontSize(12)
            }.width('100%')
            Progress({ value: this.view.progress.percent, total: 100, type: ProgressType.Linear })
              .width('100%').color(this.palette().primary)
          }.width('100%')
        }

        if (this.view.lastSummary.length > 0) {
          Text(this.view.lastSummary).fontColor(this.palette().text).fontSize(13).lineHeight(20)
        }

        if (this.view.partial) {
          Text('部分来源不可用，结果已标注不确定性。').fontColor('#f59e0b').fontSize(12)
        }
        if (this.view.failed) {
          Text('运行失败，可刷新重试或返回。').fontColor(this.palette().danger).fontSize(12)
        }

        if (this.view.artifactId !== null && this.view.artifactId.length > 0) {
          Row({ space: 6 }) {
            SymbolGlyph($r('sys.symbol.doc')).fontSize(16).fontColor([this.palette().primary])
            Text('查看产物').fontColor(this.palette().primary).fontSize(13)
          }.onClick(() => this.onOpenArtifact(this.view.artifactId))
        }

        if (this.view.events.length > 0) {
          Column({ space: 6 }) {
            ForEach(this.view.events.slice(-8), (event: AgentEvent) => {
              Row({ space: 8 }) {
                Text(this.eventLabel(event.type))
                  .fontSize(11).fontColor(this.palette().primary).layoutWeight(1)
                Text(event.summary).fontColor(this.palette().muted).fontSize(11).maxLines(1).layoutWeight(2)
              }.width('100%')
            }, (event: AgentEvent) => event.id)
          }.width('100%').padding({ top: 8 }).border({ width: { top: 1 }, color: this.palette().line })
        }
      }.width('100%').padding(16)
      .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur)
      .border({ width: 1, color: this.palette().glass.border }).borderRadius(18)
    }
  }
}