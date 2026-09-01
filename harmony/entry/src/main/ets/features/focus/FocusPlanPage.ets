import { FocusPlan, FocusPlanStep, TaskItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct FocusPlanPage {
  @Prop tasks: TaskItem[] = [];
  @Prop plan?: FocusPlan = undefined;
  @Prop loading: boolean = false;
  @Prop error: string = '';
  @Prop darkMode: boolean = false;
  onBack: () => void = () => {};
  onGenerate: (task: TaskItem) => void = () => {};
  onStartCurrent: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  @Builder Step(step: FocusPlanStep) {
    Row({ space: 10 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(step.status === 'COMPLETED' ? $r('sys.symbol.checkmark_circle_fill') : $r('sys.symbol.circle')).fontSize(20).fontColor([step.status === 'COMPLETED' ? this.palette().success : this.palette().primary])
      }.width(28).height(28)
      Column({ space: 4 }) {
        Text(step.title).fontColor(this.palette().text).fontSize(14).fontWeight(step.status === 'PENDING' ? FontWeight.Bold : FontWeight.Regular)
        Text(step.status === 'PENDING' ? `当前可执行 · 预计 ${step.estimatedMinutes} 分钟` : step.completionCriteria).fontColor(this.palette().muted).fontSize(11).lineHeight(16)
        if (step.knowledgeSource !== undefined && step.knowledgeSource.length > 0) Text(`参考：${step.knowledgeSource}`).fontColor(this.palette().primary).fontSize(10)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding({ top: 9, bottom: 9 }).alignItems(VerticalAlign.Top)
  }
  build() {
    Column() {
      SecondaryHeader({ title: '任务规划', subtitle: '把一个待办拆成清晰、可完成的下一步', darkMode: this.darkMode, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          if (this.plan !== undefined) {
            Column({ space: 8 }) {
              Text(this.plan.taskTitle).fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
              Text(this.plan.goal).fontColor(this.palette().muted).fontSize(12).lineHeight(18)
              Divider().color(this.palette().line)
              ForEach(this.plan.steps, (step: FocusPlanStep) => this.Step(step), (step: FocusPlanStep): string => step.stepNumber.toString())
              Button('按当前步骤开始专注').width('100%').height(50).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(18).onClick(() => this.onStartCurrent())
            }.width('100%').padding(16).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(22)
          } else {
            Text('从待办中选择一项，CampusMate 会生成可执行步骤。').fontColor(this.palette().muted).fontSize(12).lineHeight(18).width('100%')
          }
          Text('选择待办').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold).width('100%')
          if (this.loading) LoadingProgress().width(32).height(32).color(this.palette().primary).margin(20)
          else ForEach(this.tasks.filter((task: TaskItem): boolean => task.status !== 'completed'), (task: TaskItem) => {
            Row({ space: 10 }) { SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(19).fontColor([this.palette().primary]); Column({ space: 4 }) { Text(task.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1); Text(task.description ?? '生成专注步骤').fontColor(this.palette().muted).fontSize(11).maxLines(2) }.layoutWeight(1).alignItems(HorizontalAlign.Start); SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(15).fontColor([this.palette().muted]) }.width('100%').padding(14).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(18).alignItems(VerticalAlign.Center).onClick(() => this.onGenerate(task))
          }, (task: TaskItem): string => task.id)
          if (this.error.length > 0) Text(this.error).fontColor('#FFD14343').fontSize(12).lineHeight(18).width('100%')
          Blank().height(18)
        }.width('100%').padding({ left: 16, right: 16, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
