import { ExamItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct ExamsPage {
  @Prop exams: ExamItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @State filter: string = '全部';
  @State selectedId: string = '';
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  selectedExam(): ExamItem | undefined { return this.exams.find((item: ExamItem) => item.id === this.selectedId); }

  @Builder Hero() {
    Stack({ alignContent: Alignment.BottomStart }) {
      Image($r('app.media.exam_calendar_hero')).width('100%').height(188).objectFit(ImageFit.Cover)
      Column({ space: 8 }) {
        Text('距离最近考试').fontColor('#E6FFFFFF').fontSize(12).fontWeight(FontWeight.Medium)
        Text(this.exams.length > 0 ? this.exams[0].course_name : '暂无考试安排')
          .fontColor('#FFFFFFFF').fontSize(24).fontWeight(FontWeight.Bold).maxLines(1)
        Row({ space: 14 }) {
          Row({ space: 4 }) {
            SymbolGlyph($r('sys.symbol.calendar')).fontSize(14).fontColor(['#FFFFFFFF'])
            Text(this.exams.length > 0 ? this.exams[0].exam_date : '安心备考').fontColor('#FFFFFFFF').fontSize(11)
          }
          Row({ space: 4 }) {
            SymbolGlyph($r('sys.symbol.location_up')).fontSize(14).fontColor(['#FFFFFFFF'])
            Text(this.exams.length > 0 ? (this.exams[0].location ?? '地点待定') : '暂无地点').fontColor('#FFFFFFFF').fontSize(11)
          }
        }
      }.width('100%').padding({ left: 17, right: 17, bottom: 16 }).alignItems(HorizontalAlign.Start)
    }.width('100%').height(188).borderRadius(20).clip(true)
  }

  @Builder FilterTabs() {
    Row({ space: 7 }) {
      ForEach(['全部','未开始','已结束'], (item: string) => {
        Text(item).layoutWeight(1).textAlign(TextAlign.Center).fontSize(12)
          .fontColor(this.filter === item ? '#FFFFFFFF' : this.palette().muted)
          .fontWeight(this.filter === item ? FontWeight.Bold : FontWeight.Normal)
          .padding({ top: 9, bottom: 9 }).backgroundColor(this.filter === item ? this.palette().primary : this.palette().surface)
          .border({ width: 1, color: this.filter === item ? this.palette().primary : this.palette().line }).borderRadius(18)
          .onClick(() => this.filter = item)
      })
    }.width('100%')
  }

  @Builder ExamCard(exam: ExamItem) {
    Row({ space: 12 }) {
      Column({ space: 2 }) {
        Text(exam.exam_date.substring(Math.max(0, exam.exam_date.length - 5))).fontColor(this.palette().primary).fontSize(14).fontWeight(FontWeight.Bold)
        Text(exam.exam_type ?? '考试').fontColor(this.palette().muted).fontSize(9)
      }.width(58).height(58).justifyContent(FlexAlign.Center).backgroundColor(this.palette().soft).borderRadius(14)
      Column({ space: 5 }) {
        Text(exam.course_name).fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold).maxLines(1)
        Row({ space: 4 }) {
          SymbolGlyph($r('sys.symbol.clock')).fontSize(12).fontColor([this.palette().muted])
          Text(`${exam.start_time ?? '--:--'} - ${exam.end_time ?? '--:--'}`).fontColor(this.palette().muted).fontSize(10)
        }
        Row({ space: 4 }) {
          SymbolGlyph($r('sys.symbol.location_up')).fontSize(12).fontColor([this.palette().muted])
          Text(`${exam.location ?? '地点待定'}  ${exam.seat_number ?? ''}`).fontColor(this.palette().muted).fontSize(10).maxLines(1)
        }
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      SymbolGlyph($r('sys.symbol.bell')).fontSize(18).fontColor([exam.reminder_enabled === false ? this.palette().muted : this.palette().primary])
    }.width('100%').padding(13).backgroundColor(this.palette().surface)
      .border({ width: 1, color: this.palette().line }).borderRadius(18)
      .onClick(() => this.selectedId = exam.id)
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))
      .gesture(
        TapGesture({ count: 1 })
          .onAction(() => {
            animateTo({ duration: 150, curve: Curve.EaseInOut }, () => {
            })
          })
      )
  }

  @Builder Detail(exam: ExamItem) {
    Scroll() {
      Column({ space: 13 }) {
        Stack({ alignContent: Alignment.BottomStart }) {
          Image($r('app.media.exam_calendar_hero')).width('100%').height(202).objectFit(ImageFit.Cover)
          Column({ space: 5 }) {
            Text(exam.course_name).fontColor('#FFFFFFFF').fontSize(24).fontWeight(FontWeight.Bold).maxLines(2)
            Text(exam.exam_type ?? '课程考试').fontColor('#DFFFFFFF').fontSize(11)
          }.padding({ left: 16, right: 16, bottom: 16 }).alignItems(HorizontalAlign.Start)
        }.width('100%').height(202).borderRadius(20).clip(true)
        Column() {
          this.DetailRow($r('sys.symbol.calendar'), '考试日期', exam.exam_date)
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.clock'), '考试时间', `${exam.start_time ?? '--:--'} - ${exam.end_time ?? '--:--'}`)
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.location_up'), '考试地点', exam.location ?? '待定')
          Divider().color(this.palette().line)
          this.DetailRow($r('sys.symbol.person'), '座位号', exam.seat_number ?? '待定')
        }.width('100%').padding({ left: 14, right: 14 }).backgroundColor(this.palette().surface).borderRadius(18)
        if ((exam.notes ?? '').length > 0) {
          Text(exam.notes ?? '').fontColor(this.palette().muted).fontSize(12).lineHeight(19).width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(16)
        }
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
      SecondaryHeader({ title: this.selectedId.length > 0 ? '考试详情' : '考试安排', subtitle: this.selectedId.length > 0 ? '时间、地点与座位信息' : '每一场考试，都替你记得清清楚楚', darkMode: this.darkMode, onBack: () => this.selectedId.length > 0 ? this.selectedId = '' : this.onBack() })
      if (this.selectedExam() !== undefined) {
        this.Detail(this.selectedExam()!)
      } else {
      Scroll() {
        Column({ space: 12 }) {
          this.Hero()
          this.FilterTabs()
          Row() {
            Text('考试列表').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
            Blank()
            Text(`${this.exams.length} 场`).fontColor(this.palette().muted).fontSize(11)
          }.width('100%')
          if (this.loading) {
            LoadingProgress().width(34).height(34).color(this.palette().primary).margin({ top: 28 })
          } else if (this.exams.length === 0) {
            Column({ space: 10 }) {
              SymbolGlyph($r('sys.symbol.calendar')).fontSize(34).fontColor([this.palette().muted])
              Text('暂无考试安排').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
              Text('下拉刷新或稍后再查看').fontColor(this.palette().muted).fontSize(11)
            }.width('100%').padding({ top: 34, bottom: 34 }).onClick(() => this.onRefresh())
          } else {
            ForEach(this.exams, (exam: ExamItem) => { this.ExamCard(exam) }, (exam: ExamItem) => exam.id)
          }
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
