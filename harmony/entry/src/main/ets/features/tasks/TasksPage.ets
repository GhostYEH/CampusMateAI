import { TaskCreateRequest, TaskImportAnalyzeResponse, TaskImportCommitResponse, TaskImportDraft, TaskItem } from '../../data/Models';
import { closedTaskImportState, copyImportDraft, selectedImportTasks, TaskImportClosedState } from './TaskImportModel';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';

function importanceLabel(importance: string): string {
  if (importance === 'urgent') return '紧急';
  if (importance === 'high') return '学业关键';
  if (importance === 'important') return '较重要';
  if (importance === 'normal') return '普通';
  if (importance === 'low') return '次要';
  return '待评';
}
function importanceBgColor(importance: string): string {
  if (importance === 'urgent') return '#FFE0E3';
  if (importance === 'high') return '#FFEBED';
  if (importance === 'important') return '#FFF4DD';
  if (importance === 'normal') return '#EEF1F6';
  if (importance === 'low') return '#E8F7F0';
  return '#EEF1F6';
}
function importanceFgColor(importance: string): string {
  if (importance === 'urgent') return '#D6394B';
  if (importance === 'high') return '#DD6570';
  if (importance === 'important') return '#DA9739';
  if (importance === 'normal') return '#6B7280';
  if (importance === 'low') return '#3E9E7F';
  return '#9CA3AF';
}

@Component({ freezeWhenInactive: true })
export struct TasksPage {
  @Prop tasks: TaskItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State filter: string = '待完成';
  @State importOpen: boolean = false;
  @State importSource: string = '学习材料';
  @State importContent: string = '';
  @State importBusy: boolean = false;
  @State importError: string = '';
  @State importResult?: TaskImportAnalyzeResponse = undefined;
  @State importDrafts: TaskImportDraft[] = [];
  onRefresh: () => void = () => {};
  onComplete: (id: string) => void = () => {};
  onOpenDetail: (task: TaskItem) => void = (_: TaskItem) => {};
  onAnalyzeImport: (content: string, sourceName: string) => Promise<TaskImportAnalyzeResponse> = async (_: string, __: string) => ({ mode: 'rules', split_reason: '', needs_user_confirmation: false, tasks: [] });
  onCommitImport: (tasks: TaskCreateRequest[]) => Promise<TaskImportCommitResponse> = async (_: TaskCreateRequest[]) => ({ created: [], skipped_existing: [] });
  onOpenFocus: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  pendingCount(): number { return this.tasks.filter((task: TaskItem) => task.status !== 'completed').length; }
  selectedImportCount(): number { return selectedImportTasks(this.importDrafts).length; }

  resetImportState(): void {
    const state: TaskImportClosedState = closedTaskImportState();
    this.importOpen = state.open;
    this.importResult = state.result;
    this.importDrafts = state.drafts;
    this.importError = state.error;
  }

  closeImport(): void {
    if (this.importBusy) return;
    this.resetImportState();
  }

  updateImportDraft(index: number, draft: TaskImportDraft): void {
    this.importDrafts = this.importDrafts.map((item: TaskImportDraft, position: number) => position === index ? draft : item);
  }

  async analyzeImport(): Promise<void> {
    if (this.importContent.trim().length === 0 || this.importBusy) return;
    this.importBusy = true; this.importError = '';
    try {
      const result: TaskImportAnalyzeResponse = await this.onAnalyzeImport(this.importContent.trim(), this.importSource.trim());
      this.importResult = result;
      this.importDrafts = result.tasks.map((task: TaskImportDraft): TaskImportDraft => copyImportDraft(task, task.title, task.description, task.selected));
    } catch (_) { this.importError = '材料分析失败，请检查网络后重试'; }
    finally { this.importBusy = false; }
  }

  async commitImport(): Promise<void> {
    if (this.importBusy) return;
    const selected: TaskImportDraft[] = selectedImportTasks(this.importDrafts);
    if (selected.length === 0) return;
    this.importBusy = true; this.importError = '';
    try {
      const requests: TaskCreateRequest[] = selected.map((task: TaskImportDraft): TaskCreateRequest => ({ title: task.title, description: task.description, deadline: task.deadline, source_name: task.source_name, source_text: task.source_text, priority: task.priority }));
      await this.onCommitImport(requests); this.resetImportState();
    } catch (_) { this.importError = '保存导入任务失败，请重试'; }
    finally { this.importBusy = false; }
  }

  @Builder Hero() {
    Row() {
      Column({ space: 7 }) {
        Text('今日进度').fontColor(this.palette().muted).fontSize(12)
        Text(this.pendingCount() === 0 ? '都完成啦' : `还有 ${this.pendingCount()} 项`)
          .fontColor(this.palette().text).fontSize(24).fontWeight(FontWeight.Bold)
        Text('专注当下，不必一次做完所有事').fontColor(this.palette().muted).fontSize(11)
        Row({ space: 6 }) {
          SymbolGlyph($r('sys.symbol.bolt')).fontSize(16).fontColor([this.palette().accent])
          Text('优先处理临近截止任务').fontColor(this.palette().text).fontSize(11)
        }
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Stack({ alignContent: Alignment.Center }) {
        Progress({ value: this.tasks.length === 0 ? 0 : (this.tasks.length - this.pendingCount()) * 100 / this.tasks.length, total: 100, type: ProgressType.Ring })
          .width(72).height(72).color(this.palette().primary).backgroundColor(this.palette().line).style({ strokeWidth: 7 })
        Text(this.tasks.length === 0 ? '0%' : `${Math.round((this.tasks.length - this.pendingCount()) * 100 / this.tasks.length)}%`)
          .fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Bold)
      }
    }.width('100%').height(164).padding(20).alignItems(VerticalAlign.Center)
      .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).border({ width: 1, color: this.palette().glass.border }).borderRadius(24)
  }

  @Builder TaskCard(task: TaskItem) {
    Row({ space: 10 }) {
      Toggle({ type: ToggleType.Checkbox, isOn: task.status === 'completed' })
        .selectedColor(this.palette().success).onChange(() => this.onComplete(task.id))
      Column({ space: 5 }) {
        Text(task.title).fontColor(task.status === 'completed' ? this.palette().muted : this.palette().text)
          .fontSize(14).fontWeight(FontWeight.Medium).maxLines(2)
          .decoration({ type: task.status === 'completed' ? TextDecorationType.LineThrough : TextDecorationType.None })
        Row({ space: 7 }) {
          SymbolGlyph($r('sys.symbol.clock')).fontSize(14).fontColor([this.palette().accent])
          Text(task.deadline ?? task.due ?? '待设置').fontColor(this.palette().muted).fontSize(11)
          Text('·').fontColor(this.palette().muted)
          Text(task.source_name ?? '个人安排').fontColor(this.palette().muted).fontSize(11)
          if (task.importance && task.importance !== 'unknown') {
            Text(importanceLabel(task.importance))
              .fontColor(importanceFgColor(task.importance))
              .fontSize(10)
              .backgroundColor(importanceBgColor(task.importance))
              .borderRadius(6)
              .padding({ left: 5, right: 5, top: 2, bottom: 2 })
          }
        }
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(18).fontColor([this.palette().muted])
    }.width('100%').padding({ left: 12, right: 12, top: 12, bottom: 12 })
      .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).border({ width: 1, color: this.palette().glass.border }).borderRadius(20)
      .opacity(task.status === 'completed' ? 0.6 : 1)
      .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.STATE), curve: Curve.EaseInOut })
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
      .onClick(() => this.onOpenDetail(task))
  }

  @Builder Header() {
    Row() {
      Column({ space: 3 }) {
        Text('待办').fontColor(this.palette().text).fontSize(25).fontWeight(FontWeight.Bold)
        Text('今天先完成最重要的一小步').fontColor(this.palette().muted).fontSize(11).maxLines(1)
      }.alignItems(HorizontalAlign.Start)
      Blank()
      Text('REAL')
        .fontColor(this.palette().success).fontSize(9).fontWeight(FontWeight.Bold)
        .padding({ left: 8, right: 8, top: 5, bottom: 5 })
        .backgroundColor(this.darkMode ? '#273D614A' : '#164E8C6A').borderRadius(12)
      Button('进入专注').fontSize(11).fontWeight(FontWeight.Bold).fontColor('#FFFFFF').backgroundColor(this.palette().primary)
        .borderRadius(12).padding({ left: 10, right: 10, top: 4, bottom: 4 }).onClick(() => this.onOpenFocus())
      SymbolGlyph($r('sys.symbol.square_and_arrow_down')).fontSize(21).fontColor([this.palette().primary])
        .padding(7).backgroundColor(this.palette().soft).borderRadius(11).onClick(() => this.importOpen = true)
    }.width('100%').alignItems(VerticalAlign.Top)
  }

  @Builder ImportDialog() {
    Column({ space: 14 }) {
      Row() {
        Column({ space: 3 }) {
          Text('AI TASK IMPORT').fontColor(this.palette().primary).fontSize(9).fontWeight(FontWeight.Bold)
          Text(this.importResult === undefined ? '导入学习材料' : '确认识别结果').fontColor(this.palette().text).fontSize(22).fontWeight(FontWeight.Bold)
          Text(this.importResult === undefined ? '粘贴课程计划、作业要求或清单' : '已有任务会保留原进度').fontColor(this.palette().muted).fontSize(11)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        SymbolGlyph($r('sys.symbol.xmark')).fontSize(20).fontColor([this.palette().muted]).onClick(() => this.closeImport())
      }.width('100%')
      if (this.importResult === undefined) {
        TextInput({ text: this.importSource, placeholder: '材料名称' }).height(44).borderRadius(13).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).onChange((value: string) => this.importSource = value.substring(0, 256))
        TextArea({ text: this.importContent, placeholder: '粘贴 Markdown 清单或课程通知…' }).height(210).borderRadius(13).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).onChange((value: string) => this.importContent = value.substring(0, 20000))
      } else {
        Row({ space: 6 }) { SymbolGlyph($r('sys.symbol.bolt')).fontSize(17).fontColor([this.palette().primary]); Text(`识别到 ${this.importDrafts.length} 项`).fontColor(this.palette().primary).fontSize(12).fontWeight(FontWeight.Bold); Blank(); Text(this.importResult?.split_reason ?? '').fontColor(this.palette().muted).fontSize(9) }.width('100%')
        if (this.importDrafts.length === 0) {
          Column({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.bolt')).fontSize(30).fontColor([this.palette().primary])
            Text('没有识别到可导入的待办').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
            Text('请点击“返回修改”补充或调整材料内容后再试').fontColor(this.palette().muted).fontSize(11)
          }.width('100%').padding({ top: 34, bottom: 34 }).alignItems(HorizontalAlign.Center)
        } else List({ space: 8 }) {
          ForEach(this.importDrafts, (draft: TaskImportDraft, index: number) => {
            ListItem() {
              Row({ space: 8 }) {
                Toggle({ type: ToggleType.Checkbox, isOn: draft.selected }).enabled(draft.existing_task_id === undefined).onChange((checked: boolean) => this.updateImportDraft(index, copyImportDraft(draft, draft.title, draft.description, checked)))
                Column({ space: 5 }) {
                  TextInput({ text: draft.title }).onChange((value: string) => this.updateImportDraft(index, copyImportDraft(draft, value.substring(0, 256), draft.description, draft.selected))).backgroundColor(Color.Transparent)
                  TextArea({ text: draft.description ?? '', placeholder: '备注（选填）' }).height(54).onChange((value: string) => this.updateImportDraft(index, copyImportDraft(draft, draft.title, value.substring(0, 4000), draft.selected))).backgroundColor(Color.Transparent)
                  if (draft.existing_task_id !== undefined) { Text(`已有${draft.existing_status === 'completed' ? '已完成' : '待办'}任务，保留原进度`).fontColor(this.palette().success).fontSize(9) }
                }.layoutWeight(1).alignItems(HorizontalAlign.Start)
              }.width('100%').padding(10).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).border({ width: 1, color: this.palette().glass.border }).borderRadius(16)
            }
          }, (draft: TaskImportDraft, index: number) => `${index}-${draft.title}`)
        }.height(330).width('100%')
      }
      if (this.importError.length > 0) { Text(this.importError).fontColor('#D85D68').fontSize(10).width('100%') }
      Row({ space: 8 }) {
        Blank()
        Button(this.importResult === undefined ? '取消' : '返回修改').backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).fontColor(this.palette().muted).onClick(() => { if (this.importResult === undefined) this.closeImport(); else { this.importResult = undefined; this.importDrafts = []; } })
        Button(this.importBusy ? '处理中…' : (this.importResult === undefined ? '分析并拆分' : `保存 ${this.selectedImportCount()} 项`)).backgroundColor(this.palette().primary).fontColor('#FFFFFF').enabled(!this.importBusy && (this.importResult === undefined ? this.importContent.trim().length > 0 : this.selectedImportCount() > 0)).onClick(() => { if (this.importResult === undefined) this.analyzeImport(); else this.commitImport(); })
      }.width('100%')
    }.width('92%').constraintSize({ maxWidth: 720 }).padding(20).backgroundColor(this.darkMode ? '#CC17243A' : '#DDF8FBFF').backdropBlur(28).border({ width: 1, color: '#99FFFFFF' }).borderRadius(24)
  }

  build() {
    Stack({ alignContent: Alignment.Center }) {
    Column() {
      Scroll() {
        Column({ space: 14 }) {
          this.Header()
          this.Hero()
          Row({ space: 8 }) {
            ForEach(['待完成','已完成','全部'], (item: string) => {
              Text(item).fontColor(this.filter === item ? this.palette().primary : this.palette().muted).fontSize(12)
                .padding({ left: 13, right: 13, top: 8, bottom: 8 })
                .backgroundColor(this.filter === item ? this.palette().soft : this.palette().surface)
                .border({ width: 1, color: this.palette().glass.border }).borderRadius(12)
                .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.STATE), curve: Curve.EaseInOut })
                .onClick(() => this.filter = item)
            })
          }
          Row() { Text(this.filter).fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold); Blank(); Text(`${this.tasks.length} 项`).fontColor(this.palette().muted).fontSize(12) }.width('100%')
          if (this.loading && this.tasks.length === 0) {
            LoadingProgress().width(36).height(36).color(this.palette().primary).margin({ top: 32 })
          } else if (this.tasks.length === 0) {
            Column({ space: 8 }) {
              SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(38).fontColor([this.palette().success])
              Text('待办已清空，做得不错').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
              Text('给自己留一点休息时间吧').fontColor(this.palette().muted).fontSize(12)
            }.padding({ top: 48, bottom: 48 }).onClick(() => this.onRefresh())
          } else {
            ForEach(this.tasks.filter((task: TaskItem) => this.filter === '全部' || (this.filter === '已完成' ? task.status === 'completed' : task.status !== 'completed')),
              (task: TaskItem) => { this.TaskCard(task) }, (task: TaskItem) => task.id)
          }
          Blank().height(112)
        }.width('100%').padding({ left: 16, right: 16, top: 12, bottom: 10 })
      }.width('100%').height('100%').scrollBar(BarState.Off).backgroundColor(this.palette().background)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
    if (this.importOpen) {
      Column() {}.width('100%').height('100%').backgroundColor('#66303D5F').backdropBlur(8).onClick(() => this.closeImport())
      this.ImportDialog()
    }
    }.width('100%').height('100%')
  }
}
