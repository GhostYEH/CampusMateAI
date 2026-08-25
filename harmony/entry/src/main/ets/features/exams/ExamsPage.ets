import { ExamItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';

@Component
export struct ExamsPage {
  @Prop exams: ExamItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State filter: string = '全部';
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  onOpenDetail: (exam: ExamItem) => void = (_: ExamItem) => {};
  onOpenForm: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  filteredExams(): ExamItem[] {
    if (this.filter === '全部') return this.exams;
    const now: string = new Date().toISOString().substring(0, 10);
    if (this.filter === '未开始') return this.exams.filter((e: ExamItem) => (e.exam_date ?? '') >= now);
    return this.exams.filter((e: ExamItem) => (e.exam_date ?? '') < now);
  }

  @Builder PageHeader() {
    Row({ space: 12 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.arrow_left')).fontSize(21).fontColor([this.palette().text])
      }
      .width(40).height(40).backgroundColor(this.palette().surface).borderRadius(20)
      .border({ width: 1, color: this.palette().line })
      .onClick(() => this.onBack())

      Text('考试安排')
        .fontColor(this.palette().text).fontSize(25).fontWeight(FontWeight.Bold)
        .layoutWeight(1)
    }.width('100%').padding({ left: 14, right: 14, top: 12, bottom: 10 }).alignItems(VerticalAlign.Center)
  }

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
        Text((exam.exam_date ?? '').substring(Math.max(0, (exam.exam_date ?? '').length - 5))).fontColor(this.palette().primary).fontSize(14).fontWeight(FontWeight.Bold)
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
      .onClick(() => this.onOpenDetail(exam))
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))

  }

  build() {
    Column() {
      this.PageHeader()
      Scroll() {
        Column({ space: 12 }) {
          Row() {
            Blank()
            Stack({ alignContent: Alignment.Center }) {
              SymbolGlyph($r('sys.symbol.plus')).fontSize(25).fontColor(['#FFFFFFFF'])
            }
            .width(48).height(48).backgroundColor(this.palette().primary).borderRadius(24)
            .onClick(() => this.onOpenForm())
          }.width('100%').padding({ right: 2, bottom: 2 })
          this.Hero()
          this.FilterTabs()
          if (this.loading) {
            LoadingProgress().width(34).height(34).color(this.palette().primary).margin({ top: 28 })
          } else if (this.exams.length === 0) {
            Column({ space: 10 }) {
              SymbolGlyph($r('sys.symbol.calendar')).fontSize(34).fontColor([this.palette().muted])
              Text('暂无考试安排').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Medium)
              Text('下拉刷新或稍后再查看').fontColor(this.palette().muted).fontSize(11)
            }.width('100%').padding({ top: 34, bottom: 34 }).onClick(() => this.onRefresh())
          } else {
            ForEach(this.filteredExams(), (exam: ExamItem) => { this.ExamCard(exam) }, (exam: ExamItem) => exam.id)
          }
        }
        .width('100%')
        .constraintSize({ minHeight: '100%' })
        .padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
