import { ExamItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { promptAction } from '@kit.ArkUI';

@Component
export struct ExamsPage {
  @Prop exams: ExamItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @State filter: string = '全部';
  @State selectedId: string = '';
  @State showEdit: boolean = false;
  @State editId: string = '';
  @State formCourseName: string = '';
  @State formExamDate: string = '';
  @State formStartTime: string = '';
  @State formEndTime: string = '';
  @State formLocation: string = '';
  @State formSeatNumber: string = '';
  @State formExamType: string = '';
  @State formNotes: string = '';
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  onSave: (payload: ExamItem, id?: string) => void = () => {};
  onDelete: (id: string) => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  selectedExam(): ExamItem | undefined { return this.exams.find((item: ExamItem) => item.id === this.selectedId); }
  filteredExams(): ExamItem[] {
    if (this.filter === '全部') return this.exams;
    const now: string = new Date().toISOString().substring(0, 10);
    if (this.filter === '未开始') return this.exams.filter((e: ExamItem) => (e.exam_date ?? '') >= now);
    return this.exams.filter((e: ExamItem) => (e.exam_date ?? '') < now);
  }

  startEdit(exam?: ExamItem): void {
    if (exam !== undefined) {
      this.editId = exam.id;
      this.formCourseName = exam.course_name;
      this.formExamDate = exam.exam_date;
      this.formStartTime = exam.start_time ?? '';
      this.formEndTime = exam.end_time ?? '';
      this.formLocation = exam.location ?? '';
      this.formSeatNumber = exam.seat_number ?? '';
      this.formExamType = exam.exam_type ?? '';
      this.formNotes = exam.notes ?? '';
    } else {
      this.editId = '';
      this.formCourseName = '';
      this.formExamDate = '';
      this.formStartTime = '';
      this.formEndTime = '';
      this.formLocation = '';
      this.formSeatNumber = '';
      this.formExamType = '';
      this.formNotes = '';
    }
    this.showEdit = true;
  }

  submitEdit(): void {
    if (this.formCourseName.trim().length === 0 || this.formExamDate.trim().length === 0) return;
    const payload: ExamItem = {
      id: this.editId.length > 0 ? this.editId : `temp-${Date.now()}`,
      course_name: this.formCourseName.trim(),
      exam_date: this.formExamDate.trim(),
      start_time: this.formStartTime.trim(),
      end_time: this.formEndTime.trim(),
      location: this.formLocation.trim(),
      seat_number: this.formSeatNumber.trim(),
      exam_type: this.formExamType.trim(),
      notes: this.formNotes.trim(),
      reminder_enabled: true
    };
    this.showEdit = false;
    this.onSave(payload, this.editId.length > 0 ? this.editId : undefined);
  }

  confirmDelete(exam: ExamItem): void {
    try { promptAction.showDialog({ title: '删除考试', message: `确认删除「${exam.course_name}」?`, buttons: [{ text: '取消', color: '#667784' }, { text: '删除', color: '#C25450' }] }).then((result) => { if (result.index === 1) { this.onDelete(exam.id); this.selectedId = ''; } }); } catch { /* ignore */ }
  }

  @Builder PageHeader() {
    Row({ space: 12 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.arrow_left')).fontSize(21).fontColor([this.palette().text])
      }
      .width(40).height(40).backgroundColor(this.palette().surface).borderRadius(20)
      .border({ width: 1, color: this.palette().line })
      .onClick(() => {
        if (this.showEdit) this.showEdit = false;
        else if (this.selectedId.length > 0) this.selectedId = '';
        else this.onBack();
      })

      Text(this.showEdit ? (this.editId.length > 0 ? '编辑考试' : '添加考试') :
        this.selectedId.length > 0 ? '考试详情' : '考试安排')
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
      .onClick(() => this.selectedId = exam.id)
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))

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
        Row({ space: 10 }) {
          Button('编辑').layoutWeight(1).height(46).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').onClick(() => this.startEdit(exam))
          Button('删除').layoutWeight(1).height(46).backgroundColor(this.palette().surface).fontColor(this.palette().danger).border({ width: 1, color: this.palette().line }).onClick(() => this.confirmDelete(exam))
        }.width('100%')
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
  }

  @Builder EditForm() {
    Scroll() {
      Column({ space: 12 }) {
        Text(this.editId.length > 0 ? '编辑考试' : '添加考试').fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold).width('100%')
        TextInput({ placeholder: '课程名称 *', text: this.formCourseName }).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formCourseName = v)
        TextInput({ placeholder: '考试日期 * (YYYY-MM-DD)', text: this.formExamDate }).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formExamDate = v)
        TextInput({ placeholder: '考试类型', text: this.formExamType }).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formExamType = v)
        Row({ space: 10 }) {
          TextInput({ placeholder: '开始时间', text: this.formStartTime }).layoutWeight(1).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formStartTime = v)
          TextInput({ placeholder: '结束时间', text: this.formEndTime }).layoutWeight(1).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formEndTime = v)
        }.width('100%')
        TextInput({ placeholder: '地点', text: this.formLocation }).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formLocation = v)
        TextInput({ placeholder: '座位号', text: this.formSeatNumber }).height(50).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formSeatNumber = v)
        TextArea({ placeholder: '备注', text: this.formNotes }).height(110).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((v: string) => this.formNotes = v)
        Button('保存').width('100%').height(50).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
          .enabled(this.formCourseName.trim().length > 0 && this.formExamDate.trim().length > 0)
          .onClick(() => this.submitEdit())
        Button('取消').width('100%').height(46).backgroundColor(this.palette().soft).fontColor(this.palette().primary).onClick(() => this.showEdit = false)
      }.width('100%').padding({ left: 16, right: 16, top: 6, bottom: 24 })
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
      this.PageHeader()
      if (this.showEdit) {
        this.EditForm()
      } else if (this.selectedExam() !== undefined) {
        this.Detail(this.selectedExam()!)
      } else {
      Scroll() {
        Column({ space: 12 }) {
          Row() {
            Blank()
            Stack({ alignContent: Alignment.Center }) {
              SymbolGlyph($r('sys.symbol.plus')).fontSize(25).fontColor(['#FFFFFFFF'])
            }
            .width(48).height(48).backgroundColor(this.palette().primary).borderRadius(24)
            .onClick(() => this.startEdit())
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
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
