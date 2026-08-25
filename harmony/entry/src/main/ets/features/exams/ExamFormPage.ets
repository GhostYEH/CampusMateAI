import { ExamItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct ExamFormPage {
  @Prop exam: ExamItem = { id: '', course_name: '', exam_date: '' };
  @Prop isEditing: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State formCourseName: string = '';
  @State formExamDate: string = '';
  @State formStartTime: string = '';
  @State formEndTime: string = '';
  @State formLocation: string = '';
  @State formSeatNumber: string = '';
  @State formExamType: string = '';
  @State formNotes: string = '';
  onBack: () => void = () => {};
  onSave: (payload: ExamItem, id?: string) => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void {
    this.formCourseName = this.exam.course_name;
    this.formExamDate = this.exam.exam_date;
    this.formStartTime = this.exam.start_time ?? '';
    this.formEndTime = this.exam.end_time ?? '';
    this.formLocation = this.exam.location ?? '';
    this.formSeatNumber = this.exam.seat_number ?? '';
    this.formExamType = this.exam.exam_type ?? '';
    this.formNotes = this.exam.notes ?? '';
  }

  submit(): void {
    if (this.formCourseName.trim().length === 0 || this.formExamDate.trim().length === 0) return;
    const id: string = this.isEditing ? this.exam.id : `temp-${Date.now()}`;
    const payload: ExamItem = {
      id: id,
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
    this.onSave(payload, this.isEditing ? this.exam.id : undefined);
  }

  build() {
    Column() {
      SecondaryHeader({ title: this.isEditing ? '编辑考试' : '添加考试', subtitle: '填写考试安排信息', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 12 }) {
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
            .onClick(() => this.submit())
          Button('取消').width('100%').height(46).backgroundColor(this.palette().soft).fontColor(this.palette().primary).onClick(() => this.onBack())
        }.width('100%').padding({ left: 16, right: 16, top: 6, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
