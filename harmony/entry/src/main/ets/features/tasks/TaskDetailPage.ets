import { TaskItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct TaskDetailPage {
  @Prop task: TaskItem = { id: '', title: '', status: 'pending' };
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  onBack: () => void = () => {};
  onComplete: (id: string) => void = (_: string) => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  @Builder DetailRow(symbol: Resource, label: string, value: string) {
    Row({ space: 11 }) {
      SymbolGlyph(symbol).fontSize(19).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().muted).fontSize(11).width(74)
      Text(value).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).layoutWeight(1)
    }.width('100%').padding({ top: 14, bottom: 14 })
  }

  build() {
    Column() {
      SecondaryHeader({ title: '待办详情', subtitle: '查看待办详细信息', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          Column({ space: 8 }) {
            Text(this.task.title).fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold).width('100%')
            Row({ space: 8 }) {
              Text(this.task.status === 'completed' ? '已完成' : '待完成')
                .fontColor(this.task.status === 'completed' ? this.palette().success : this.palette().accent).fontSize(11).fontWeight(FontWeight.Bold)
                .padding({ left: 8, right: 8, top: 4, bottom: 4 }).backgroundColor(this.palette().soft).borderRadius(10)
              Text(this.task.source_name ?? '个人安排').fontColor(this.palette().muted).fontSize(11)
            }
          }.width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)
          Column() {
            this.DetailRow($r('sys.symbol.text_alignleft'), '标题', this.task.title)
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.clock'), '截止时间', this.task.deadline ?? this.task.due ?? '待设置')
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.checkmark_circle'), '状态', this.task.status === 'completed' ? '已完成' : '待完成')
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.info_circle'), '来源', this.task.source_name ?? '个人安排')
          }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)
          if ((this.task.description ?? '').length > 0) {
            Column({ space: 6 }) {
              Text('详细描述').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
              Text(this.task.description ?? '').fontColor(this.palette().muted).fontSize(12).lineHeight(20)
            }.width('100%').padding(14).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(16)
          }
          Button(this.task.status === 'completed' ? '标记为未完成' : '标记为已完成')
            .width('100%').height(48).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
            .onClick(() => { this.onComplete(this.task.id); this.onBack(); })
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
