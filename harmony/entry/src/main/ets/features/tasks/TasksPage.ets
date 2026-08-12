import { TaskItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct TasksPage {
  @Prop tasks: TaskItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @State filter: string = '待完成';
  @State selectedId: string = '';
  onRefresh: () => void = () => {};
  onComplete: (id: string) => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  pendingCount(): number { return this.tasks.filter((task: TaskItem) => task.status !== 'completed').length; }
  selectedTask(): TaskItem | undefined { return this.tasks.find((item: TaskItem) => item.id === this.selectedId); }

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
      .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(24)
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
        }
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(18).fontColor([this.palette().muted])
    }.width('100%').padding({ left: 12, right: 12, top: 12, bottom: 12 })
      .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(20)
      .opacity(task.status === 'completed' ? 0.6 : 1)
      .animation({ duration: 300, curve: Curve.EaseInOut })
      .onClick(() => this.selectedId = task.id)
  }

  @Builder TaskDetail(task: TaskItem) {
    Scroll() {
      Column({ space: 13 }) {
        Column({ space: 8 }) {
          Text(task.title).fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold).width('100%')
          Row({ space: 8 }) {
            Text(task.status === 'completed' ? '已完成' : '待完成')
              .fontColor(task.status === 'completed' ? this.palette().success : this.palette().accent).fontSize(11).fontWeight(FontWeight.Bold)
              .padding({ left: 8, right: 8, top: 4, bottom: 4 }).backgroundColor(this.palette().soft).borderRadius(10)
            Text(task.source_name ?? '个人安排').fontColor(this.palette().muted).fontSize(11)
          }
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
        Column() {
          this.DetailRow($r('sys.symbol.text_alignleft'), '标题', task.title)
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.clock'), '截止时间', task.deadline ?? task.due ?? '待设置')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.checkmark_circle'), '状态', task.status === 'completed' ? '已完成' : '待完成')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.info_circle'), '来源', task.source_name ?? '个人安排')
        }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().surface).borderRadius(18)
        if ((task.description ?? '').length > 0) {
          Column({ space: 6 }) {
            Text('详细描述').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
            Text(task.description ?? '').fontColor(this.palette().muted).fontSize(12).lineHeight(20)
          }.width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(16)
        }
        Button(task.status === 'completed' ? '标记为未完成' : '标记为已完成')
          .width('100%').height(48).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
          .onClick(() => { this.onComplete(task.id); this.selectedId = ''; })
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder DetailRow(symbol: Resource, label: string, value: string) {
    Row({ space: 11 }) {
      SymbolGlyph(symbol).fontSize(19).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().muted).fontSize(11).width(74)
      Text(value).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).layoutWeight(1)
    }.width('100%').padding({ top: 14, bottom: 14 })
  }

  build() {
    Column() {
      if (this.selectedTask() !== undefined) {
        SecondaryHeader({ title: '待办详情', subtitle: '查看待办详细信息', darkMode: this.darkMode, onBack: () => this.selectedId = '' })
        this.TaskDetail(this.selectedTask()!)
      } else {
      Scroll() {
        Column({ space: 14 }) {
          Row() {
            Column({ space: 2 }) {
              Text('待办').fontColor(this.palette().text).fontSize(26).fontWeight(FontWeight.Bold)
              Text('今天先完成最重要的一小步').fontColor(this.palette().muted).fontSize(13)
            }.alignItems(HorizontalAlign.Start)
            Blank(); Text('REAL').fontColor(this.palette().success).fontSize(9).fontWeight(FontWeight.Bold)
          }.width('100%')
          this.Hero()
          Row({ space: 8 }) {
            ForEach(['待完成','已完成','全部'], (item: string) => {
              Text(item).fontColor(this.filter === item ? this.palette().primary : this.palette().muted).fontSize(12)
                .padding({ left: 13, right: 13, top: 8, bottom: 8 })
                .backgroundColor(this.filter === item ? this.palette().soft : this.palette().surface)
                .border({ width: 1, color: this.palette().line }).borderRadius(12).onClick(() => this.filter = item)
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
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
