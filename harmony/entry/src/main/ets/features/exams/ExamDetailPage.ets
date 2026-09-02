import { ExamItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { promptAction } from '@kit.ArkUI';

@Component
export struct ExamDetailPage {
  @Prop exam: ExamItem = { id: '', course_name: '', exam_date: '' };
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  onBack: () => void = () => {};
  onEdit: () => void = () => {};
  onDelete: (id: string) => void = (_: string) => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  confirmDelete(): void {
    try {
      promptAction.showDialog({
        title: '删除考试',
        message: `确认删除「${this.exam.course_name}」?`,
        buttons: [{ text: '取消', color: '#667784' }, { text: '删除', color: '#C25450' }]
      }).then((result) => {
        if (result.index === 1) {
          this.onDelete(this.exam.id);
          this.onBack();
        }
      });
    } catch (_) { /* ignore dialog failure */ }
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
      SecondaryHeader({ title: '考试详情', subtitle: '查看考试安排', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          Stack({ alignContent: Alignment.BottomStart }) {
            Image($r('app.media.exam_calendar_hero')).width('100%').height(202).objectFit(ImageFit.Cover)
            Column({ space: 5 }) {
              Text(this.exam.course_name).fontColor('#FFFFFFFF').fontSize(24).fontWeight(FontWeight.Bold).maxLines(2)
              Text(this.exam.exam_type ?? '课程考试').fontColor('#DFFFFFFF').fontSize(11)
            }.padding({ left: 16, right: 16, bottom: 16 }).alignItems(HorizontalAlign.Start)
          }.width('100%').height(202).borderRadius(20).clip(true)
          Column() {
            this.DetailRow($r('sys.symbol.calendar'), '考试日期', this.exam.exam_date)
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.clock'), '考试时间', `${this.exam.start_time ?? '--:--'} - ${this.exam.end_time ?? '--:--'}`)
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.location_up'), '考试地点', this.exam.location ?? '待定')
            Divider().color(this.palette().line)
            this.DetailRow($r('sys.symbol.person'), '座位号', this.exam.seat_number ?? '待定')
          }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)
          if ((this.exam.notes ?? '').length > 0) {
            Text(this.exam.notes ?? '').fontColor(this.palette().muted).fontSize(12).lineHeight(19).width('100%').padding(14).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(16)
          }
          Row({ space: 10 }) {
            Button('编辑').layoutWeight(1).height(46).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').onClick(() => this.onEdit())
            Button('删除').layoutWeight(1).height(46).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).fontColor(this.palette().danger).border({ width: 1, color: this.palette().glass.border }).onClick(() => this.confirmDelete())
          }.width('100%')
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
