import { AgentRuntimeRepository } from '../../repository/AgentRuntimeRepository';
import {
  CourseResearchRun, CourseResearchSource, AcademicPolicy, AssistanceMode,
  CitationVerification, RunStatus, AgentArtifact, AgentEvent
} from '../../data/AgentRuntimeModels';
import { AgentRunView, AgentEventReducer } from '../../service/AgentEventReducer';
import { AgentRunPanel } from '../agent/AgentRunPanel';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SseEvent } from '../../data/ApiClient';
import { CourseItem } from '../../data/Models';

// 课程研究页：采集 assistance mode，展示 academic_policy 与 source_policy，
// 通过 SSE 展示逻辑角色进度、引用 verified 状态、PARTIAL 与 artifact。
// 不显示模型 prompt 或隐藏推理。
@Component
export struct CourseResearchPage {
  @Prop courses: CourseItem[] = [];
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  repository: AgentRuntimeRepository | null = null;
  onBack: () => void = () => {};
  @State question: string = '';
  @State selectedCourseId: string = '';
  @State selectedMode: AssistanceMode = AssistanceMode.EXPLAIN;
  @State run: CourseResearchRun | null = null;
  @State runView: AgentRunView | null = null;
  @State sources: CourseResearchSource[] = [];
  @State artifacts: AgentArtifact[] = [];
  @State loading: boolean = false;
  @State error: string = '';
  @State active: boolean = true;
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  async aboutToAppear(): Promise<void> {
    this.active = true;
    if (this.courses.length > 0) this.selectedCourseId = this.courses[0].id;
  }

  aboutToDisappear(): void {
    this.active = false;
  }

  academicPolicyLabel(policy: AcademicPolicy): string {
    switch (policy) {
      case AcademicPolicy.ALLOWED: return '允许';
      case AcademicPolicy.LIMITED: return '受限';
      case AcademicPolicy.EXAM_RESTRICTED: return '考试限制期';
      case AcademicPolicy.AI_PROHIBITED: return '禁止 AI';
      default: return '未知';
    }
  }

  assistanceModeLabel(mode: AssistanceMode): string {
    switch (mode) {
      case AssistanceMode.HINT: return '提示';
      case AssistanceMode.EXPLAIN: return '讲解';
      case AssistanceMode.REVIEW: return '审阅';
      case AssistanceMode.FULL_SOLUTION: return '完整解答';
      default: return '未知';
    }
  }

  verificationLabel(v: CitationVerification): string {
    switch (v) {
      case CitationVerification.VERIFIED: return '已验证';
      case CitationVerification.PARTIAL: return '部分验证';
      case CitationVerification.FAILED: return '未通过';
      default: return '未知';
    }
  }

  verificationColor(v: CitationVerification): string {
    switch (v) {
      case CitationVerification.VERIFIED: return this.palette().primary;
      case CitationVerification.PARTIAL: return '#f59e0b';
      default: return this.palette().danger;
    }
  }

  questionHash(): string {
    let hash: number = 0;
    const s: string = this.question.trim();
    for (let i: number = 0; i < s.length; i++) {
      hash = (hash * 31 + s.charCodeAt(i)) & 0x7fffffff;
    }
    return hash.toString(36);
  }

  async startResearch(): Promise<void> {
    if (this.repository === null || this.question.trim().length === 0 || this.selectedCourseId.length === 0) return;
    this.loading = true;
    this.error = '';
    try {
      const run: CourseResearchRun = await this.repository.createResearchRun(
        this.selectedCourseId, this.question.trim(),
        this.selectedMode as string, this.questionHash());
      this.run = run;
      this.runView = AgentEventReducer.initial(run.run_id);
      this.subscribeRun(run.run_id);
    } catch (_) {
      this.error = '发起研究失败，请重试';
    } finally {
      this.loading = false;
    }
  }

  subscribeRun(runId: string): void {
    if (this.repository === null) return;
    this.repository.streamEvents(runId, '', (event: SseEvent) => {
      if (!this.active) return;
      try {
        const raw: Record<string, Object> = JSON.parse(event.data) as Record<string, Object>;
        if (event.id !== undefined && event.id.length > 0) raw.id = event.id;
        if (event.event.length > 0) raw.type = event.event;
        const parsed: AgentEvent = AgentEventReducer.parseEvent(raw);
        this.runView = AgentEventReducer.append(this.runView ?? AgentEventReducer.initial(runId), parsed);
      } catch (_) { /* 忽略无法解析的事件 */ }
    }).then(async () => {
      if (!this.active) return;
      const repo: AgentRuntimeRepository | null = this.repository;
      if (repo === null) return;
      try {
        this.artifacts = await repo.listResearchArtifacts(runId);
        this.sources = await repo.listResearchSources(runId);
        this.run = await repo.getResearchRun(runId);
      } catch (_) { /* 结果加载失败保留已有状态 */ }
    }).catch(() => {
      if (this.active) this.error = '事件流中断，可刷新重试';
    });
  }

  build() {
    Column() {
      SecondaryHeader({ title: '课程研究', subtitle: '在学术政策内提供讲解与引用', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 14 }) {
          if (this.error.length > 0) {
            Text(this.error).fontColor(this.palette().danger).fontSize(12)
          }

          Text('选择课程').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
          if (this.courses.length === 0) {
            Text('暂无课程').fontColor(this.palette().muted).fontSize(12)
          } else {
            Row({ space: 8 }) {
              ForEach(this.courses.slice(0, 6), (course: CourseItem) => {
                Text(course.name).fontSize(11)
                  .fontColor(this.selectedCourseId === course.id ? '#FFFFFF' : this.palette().muted)
                  .backgroundColor(this.selectedCourseId === course.id ? this.palette().primary : this.palette().surface)
                  .borderRadius(10).padding({ left: 8, right: 8, top: 5, bottom: 5 })
                  .onClick(() => this.selectedCourseId = course.id)
              })
            }.width('100%')
          }

          Text('辅助方式').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
          Row({ space: 8 }) {
            ForEach([AssistanceMode.HINT, AssistanceMode.EXPLAIN, AssistanceMode.REVIEW, AssistanceMode.FULL_SOLUTION], (mode: AssistanceMode) => {
              Text(this.assistanceModeLabel(mode)).fontSize(11).layoutWeight(1).textAlign(TextAlign.Center)
                .fontColor(this.selectedMode === mode ? '#FFFFFF' : this.palette().muted)
                .backgroundColor(this.selectedMode === mode ? this.palette().primary : this.palette().surface)
                .borderRadius(10).padding({ top: 6, bottom: 6 })
                .onClick(() => this.selectedMode = mode)
            })
          }.width('100%')

          TextInput({ text: this.question, placeholder: '输入你的课程问题' })
            .width('100%').height(44).fontSize(14)
            .backgroundColor(this.palette().surface).borderRadius(12)
            .onChange((value: string) => this.question = value)
          Button(this.loading ? '发起中…' : '开始研究')
            .width('100%').height(46)
            .backgroundColor(this.palette().primary).fontColor('#FFFFFF').borderRadius(14)
            .enabled(!this.loading && this.question.trim().length > 0 && this.selectedCourseId.length > 0)
            .onClick(() => this.startResearch())

          if (this.run !== null) {
            Column({ space: 6 }) {
              Row({ space: 10 }) {
                Text('学术政策').fontColor(this.palette().muted).fontSize(11)
                Text(this.academicPolicyLabel(this.run.academic_policy))
                  .fontColor(this.verificationColor(CitationVerification.VERIFIED)).fontSize(11)
                Text('来源策略').fontColor(this.palette().muted).fontSize(11)
                Text(this.run.source_policy.allow_web ? '允许网络' : '仅课程资料')
                  .fontColor(this.palette().primary).fontSize(11)
              }.width('100%')
            }.width('100%').padding(10)
            .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
          }

          AgentRunPanel({
            view: this.runView,
            darkMode: this.darkMode,
            reduceMotion: this.reduceMotion,
            onOpenArtifact: (artifactId: string) => { if (this.repository !== null) this.repository.downloadArtifact(artifactId); },
            onCancel: () => { if (this.repository !== null && this.run !== null) this.repository.cancelResearchRun(this.run.run_id); }
          })

          if (this.sources.length > 0) {
            Text('引用来源').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
            ForEach(this.sources, (source: CourseResearchSource) => {
              Row({ space: 8 }) {
                Text(source.title).fontColor(this.palette().text).fontSize(12).maxLines(1).layoutWeight(1)
                Text(this.verificationLabel(source.verification))
                  .fontColor(this.verificationColor(source.verification)).fontSize(11)
              }.width('100%').padding(10)
              .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
            }, (source: CourseResearchSource) => source.source_id)
          }

          if (this.artifacts.length > 0) {
            Text('研究报告').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
            ForEach(this.artifacts, (artifact: AgentArtifact) => {
              Row({ space: 8 }) {
                SymbolGlyph($r('sys.symbol.doc')).fontSize(16).fontColor([this.palette().primary])
                Text(`报告 v${artifact.version}`).fontColor(this.palette().primary).fontSize(13).layoutWeight(1)
              }.width('100%').padding(10)
              .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
              .onClick(() => { if (this.repository !== null) this.repository.downloadArtifact(artifact.artifact_id); })
            }, (artifact: AgentArtifact) => artifact.artifact_id)
          }
        }.width('100%').padding({ left: 16, right: 16, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
