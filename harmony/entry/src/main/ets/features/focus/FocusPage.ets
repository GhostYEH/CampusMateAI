import { FocusMode, FocusPlan, FocusPlanStep, StudySession } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';
import { FocusCountdownRunToken, FocusLobbyStep, FocusPresentationState } from './FocusPresentationState';
import { FocusRobot } from './FocusRobot';

export type FocusSessionMode = 'QUIET' | 'AI_COMPANION' | 'SMART_GUARD';

interface FocusModeOption { id: FocusSessionMode; title: string; detail: string; symbol: Resource; }
const MODES: FocusModeOption[] = [
  { id: 'QUIET', title: '安静专注', detail: '只保留倒计时，减少打扰', symbol: $r('sys.symbol.timer') },
  { id: 'AI_COMPANION', title: 'AI 陪伴', detail: '需要时和 CampusMate 聊一聊', symbol: $r('sys.symbol.paperplane_fill') },
  { id: 'SMART_GUARD', title: '智能监督', detail: 'AI 陪伴与学习状态观察', symbol: $r('sys.symbol.eye') }
];

@Component
export struct FocusPage {
  @Prop sessions: StudySession[] = [];
  @Prop activeSession?: StudySession = undefined;
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop focusAssistDetail: string = '正在准备本地模型';
  @Prop focusAssistLabel: string = '';
  @Prop focusAssistConfidence: number = 0;
  @Prop behaviorReminder: string = '';
  @Prop plan?: FocusPlan = undefined;
  @State step: FocusLobbyStep = 'GREETING';
  @State selectedMinutes: number = 25;
  @State customMinutes: string = '60';
  @State sessionMode: FocusSessionMode = 'QUIET';
  @State typedGuide: string = '';
  @State countdown: number = 0;
  @State pressed: boolean = false;
  private typewriterTimer: number = -1;
  private countdownTimer: number = -1;
  private readonly countdownToken: FocusCountdownRunToken = new FocusCountdownRunToken();
  onBack: () => void = () => {};
  onStart: (mode: FocusMode, durationSeconds: number, sessionMode: FocusSessionMode) => void = () => {};
  onResumeActive: () => void = () => {};
  onOpenPlan: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  aboutToAppear(): void { this.playTypewriter(); }
  aboutToDisappear(): void { this.stopTypewriter(); this.stopCountdown(); }
  stopTypewriter(): void { if (this.typewriterTimer >= 0) { clearInterval(this.typewriterTimer); this.typewriterTimer = -1; } }
  guideText(): string {
    if (this.step === 'ASK_DURATION') return '这段时间想留给自己多久？';
    if (this.step === 'ASK_MODE') return '选一种陪伴方式，我们就出发。';
    if (this.step === 'CONFIRM') return '准备好了。三秒后，专注空间为你打开。';
    return '你好，我是 CampusMate。先帮你把注意力带回当下。';
  }
  playTypewriter(): void {
    this.stopTypewriter();
    const message = this.guideText();
    if (this.reduceMotion) { this.typedGuide = message; return; }
    this.typedGuide = '';
    let index = 0;
    this.typewriterTimer = setInterval(() => { index += 1; this.typedGuide = message.substring(0, index); if (index >= message.length) this.stopTypewriter(); }, 28);
  }
  changeStep(step: FocusLobbyStep): void { this.step = step; this.playTypewriter(); }
  durationSeconds(): number { return FocusPresentationState.durationSeconds(this.selectedMinutes === 0 ? Number(this.customMinutes) : this.selectedMinutes); }
  completed(): StudySession[] { return this.sessions.filter((item: StudySession) => item.status === 'completed'); }
  currentPlanStep(): FocusPlanStep | undefined {
    return this.plan?.steps.find((item: FocusPlanStep): boolean => item.status === 'PENDING');
  }
  totalMinutes(): number { return Math.floor(this.completed().reduce((sum: number, item: StudySession) => sum + item.duration_seconds, 0) / 60); }
  stopCountdown(): void {
    this.countdownToken.cancel();
    if (this.countdownTimer >= 0) clearTimeout(this.countdownTimer);
    this.countdownTimer = -1;
    this.countdown = 0;
  }
  startCountdown(): void {
    if (this.countdown > 0) return;
    this.countdown = 3;
    const version: number = this.countdownToken.begin();
    const tick = (): void => {
      if (!this.countdownToken.isCurrent(version)) return;
      if (this.countdown > 1) {
        this.countdown -= 1;
        this.countdownTimer = setTimeout(tick, this.reduceMotion ? 0 : 680);
      } else {
        this.countdown = 0;
        this.countdownTimer = -1;
        this.countdownToken.cancel();
        this.onStart('focus', this.durationSeconds(), this.sessionMode);
      }
    };
    this.countdownTimer = setTimeout(tick, this.reduceMotion ? 0 : 680);
  }

  @Builder GuideScene() {
    Stack({ alignContent: Alignment.Center }) {
      Column() {}.width('100%').height('100%').linearGradient({ angle: 135, colors: this.darkMode ? [['#FF0E1B3E', 0], ['#FF293661', 0.55], ['#FF1F4B62', 1]] : [['#FFDEE7FF', 0], ['#FFEDE9FF', 0.55], ['#FFD5F3EE', 1]] })
      Circle().width(120).height(120).fill('#3AFFFFFF').position({ x: '70%', y: '-8%' })
      Circle().width(84).height(84).fill('#2AFFFFFF').position({ x: '4%', y: '71%' })
      Text('✦').fontSize(25).fontColor('#CCFFFFFF').position({ x: '14%', y: '17%' })
      Text('✦').fontSize(18).fontColor('#CCFFFFFF').position({ x: '84%', y: '40%' })
      Column({ space: 8 }) {
        FocusRobot({ state: this.step === 'ASK_DURATION' ? 'LISTENING' : this.step === 'ASK_MODE' ? 'THINKING' : this.step === 'CONFIRM' ? 'HAPPY' : 'IDLE', darkMode: this.darkMode, reduceMotion: this.reduceMotion, compact: true })
        Row({ space: 5 }) { Circle().width(7).height(7).fill(this.palette().success); Text('CampusMate AI 导员').fontColor('#EEFFFFFF').fontSize(12).fontWeight(FontWeight.Bold) }.padding({ left: 10, right: 10, top: 6, bottom: 6 }).backgroundColor('#3A132A52').borderRadius(16).alignItems(VerticalAlign.Center)
      }.alignItems(HorizontalAlign.Center).margin({ top: 32 })
      Column({ space: 5 }) { Text('FOCUS · LEARN · GROW').fontColor('#D9FFFFFF').fontSize(9).fontWeight(FontWeight.Bold); Text(this.typedGuide).fontColor(this.palette().text).fontSize(14).lineHeight(21).maxLines(3) }.width('72%').padding(13).backgroundColor(this.darkMode ? '#E614272E' : '#F5FFFFFFFF').border({ width: 1, color: this.darkMode ? '#4D9CC7D0' : '#805B68F2' }).borderRadius(18).align(Alignment.TopStart).margin({ left: 14, top: 14 })
    }.width('100%').height(270).borderRadius(28).clip(true).transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
  }

  @Builder DurationChip(minutes: number, label: string) {
    Text(label).fontColor(this.selectedMinutes === minutes ? '#FFFFFFFF' : this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).layoutWeight(1).textAlign(TextAlign.Center).padding({ top: 10, bottom: 10 }).backgroundColor(this.selectedMinutes === minutes ? this.palette().primary : this.palette().background).border({ width: 1, color: this.selectedMinutes === minutes ? this.palette().primary : this.palette().line }).borderRadius(18).onClick(() => { this.selectedMinutes = minutes; })
  }
  @Builder DurationPicker() {
    Column({ space: 10 }) {
      Text('专注时间').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
      Row({ space: 8 }) { this.DurationChip(25, '25 分钟'); this.DurationChip(45, '45 分钟'); this.DurationChip(0, '自定义') }.width('100%')
      if (this.selectedMinutes === 0) TextInput({ text: this.customMinutes, placeholder: '5–240 分钟' }).width('100%').height(46).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().background).border({ width: 1, color: this.palette().line }).borderRadius(14).onChange((value: string) => { this.customMinutes = value.replace(/[^0-9]/g, ''); })
      Button('下一步').width('100%').height(48).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(18).onClick(() => this.changeStep(FocusPresentationState.nextLobbyStep('ASK_DURATION')))
    }.width('100%').padding(15).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(22)
  }
  @Builder ModePicker() {
    Column({ space: 9 }) {
      Text('专注方式').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
      ForEach(MODES, (option: FocusModeOption) => {
        Row({ space: 10 }) {
          Stack({ alignContent: Alignment.Center }) { SymbolGlyph(option.symbol).fontSize(19).fontColor([option.id === this.sessionMode ? this.palette().primary : this.palette().muted]) }.width(38).height(38).backgroundColor(option.id === this.sessionMode ? this.palette().soft : this.palette().background).borderRadius(13)
          Column({ space: 3 }) { Text(option.title).fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold); Text(option.detail).fontColor(this.palette().muted).fontSize(11) }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          if (option.id === this.sessionMode) SymbolGlyph($r('sys.symbol.checkmark_circle_fill')).fontSize(19).fontColor([this.palette().primary])
        }.width('100%').padding(11).backgroundColor(option.id === this.sessionMode ? this.palette().soft : this.palette().background).border({ width: 1, color: option.id === this.sessionMode ? this.palette().primary : this.palette().line }).borderRadius(17).alignItems(VerticalAlign.Center).onClick(() => { this.sessionMode = option.id; })
      }, (option: FocusModeOption) => option.id)
      Button('确认方式').width('100%').height(48).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(18).onClick(() => this.changeStep(FocusPresentationState.nextLobbyStep('ASK_MODE')))
    }.width('100%').padding(15).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(22)
  }
  @Builder Confirmation() {
    Column({ space: 12 }) {
      Text('这一次，只专注这一件事。').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold)
      Text(`${Math.floor(this.durationSeconds() / 60)} 分钟 · ${MODES.find((option: FocusModeOption) => option.id === this.sessionMode)?.title ?? '安静专注'}`).fontColor(this.palette().muted).fontSize(12)
      if (this.countdown > 0) Text(this.countdown.toString()).fontColor(this.palette().primary).fontSize(44).fontWeight(FontWeight.Bold).width('100%').textAlign(TextAlign.Center)
      else Button('进入专注空间').width('100%').height(52).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(20).scale({ x: this.pressed ? MotionSpec.scale(this.reduceMotion, 0.95) : 1, y: this.pressed ? MotionSpec.scale(this.reduceMotion, 0.95) : 1 }).animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut }).onClick(() => { this.pressed = true; setTimeout(() => { this.pressed = false; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS)); this.startCountdown(); })
      Text('学习状态辅助只在智能监督且已开始专注时运行，画面不会上传或保存。').fontColor(this.palette().muted).fontSize(10).lineHeight(15)
    }.width('100%').padding(17).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(22)
  }
  @Builder Setup() {
    if (this.activeSession !== undefined &&
      (this.activeSession.status === 'active' || this.activeSession.status === 'paused')) {
      Button(this.activeSession.status === 'paused' ? '继续已暂停的专注' : '返回当前专注')
        .width('100%').height(52).backgroundColor(this.palette().primary)
        .fontColor('#FFFFFFFF').borderRadius(20).onClick(() => this.onResumeActive())
    } else if (this.step === 'GREETING') {
      Button('开始安排这段专注').width('100%').height(52)
        .backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(20)
        .onClick(() => this.changeStep('ASK_DURATION'))
    } else if (this.step === 'ASK_DURATION') {
      this.DurationPicker()
    } else if (this.step === 'ASK_MODE') {
      this.ModePicker()
    } else {
      this.Confirmation()
    }
  }
  @Builder AssistPreview() {
    Row({ space: 10 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.eye')).fontSize(18).fontColor([this.palette().success]) }.width(40).height(40).backgroundColor(this.palette().soft).borderRadius(14)
      Column({ space: 3 }) { Text('学习状态辅助').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold); Text(this.focusAssistDetail).fontColor(this.palette().muted).fontSize(10).maxLines(2); if (this.focusAssistLabel.length > 0) Text(`${this.focusAssistLabel} · ${Math.round(this.focusAssistConfidence * 100)}%`).fontColor(this.palette().primary).fontSize(10) }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding(13).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(18).alignItems(VerticalAlign.Center)
  }
  @Builder PlanPreview() {
    Column({ space: 7 }) {
      Row() { Row({ space: 7 }) { SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(18).fontColor([this.palette().primary]); Text('任务规划').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold) }.alignItems(VerticalAlign.Center); Blank(); Text('查看全部').fontColor(this.palette().primary).fontSize(11).onClick(() => this.onOpenPlan()) }.width('100%')
      if (this.plan === undefined) Text('选择一个待办，让 AI 帮你拆成可执行的专注步骤。').fontColor(this.palette().muted).fontSize(11).lineHeight(17)
      else {
        Text(this.plan.taskTitle).fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Bold).maxLines(1)
        Text(this.currentPlanStep() === undefined ? '全部步骤已完成，继续保持。' : `当前步骤 · ${this.currentPlanStep()?.title} · ${this.currentPlanStep()?.estimatedMinutes} 分钟`).fontColor(this.palette().muted).fontSize(11).maxLines(2)
      }
    }.width('100%').padding(13).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(18).onClick(() => this.onOpenPlan())
  }
  @Builder Stat(label: string, value: string, unit: string, symbol: Resource) {
    Column({ space: 4 }) { SymbolGlyph(symbol).fontSize(19).fontColor([this.palette().primary]); Row({ space: 2 }) { Text(value).fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold); Text(unit).fontColor(this.palette().muted).fontSize(10) }.alignItems(VerticalAlign.Bottom); Text(label).fontColor(this.palette().muted).fontSize(10) }.layoutWeight(1).alignItems(HorizontalAlign.Center)
  }
  @Builder Stats() {
    Row({ space: 8 }) { this.Stat('累计专注', this.totalMinutes().toString(), '分钟', $r('sys.symbol.timer')); this.Stat('完成次数', this.completed().length.toString(), '次', $r('sys.symbol.checkmark_circle')); this.Stat('正在进行', this.activeSession === undefined ? '0' : '1', '次', $r('sys.symbol.flame')) }.width('100%').padding(14).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(22)
  }
  @Builder History() {
    Column({ space: 2 }) {
      Text('专注记录').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold)
      if (this.loading) LoadingProgress().width(30).height(30).color(this.palette().primary).margin(22)
      else if (this.sessions.length === 0) Text('还没有专注记录。从一个 25 分钟开始吧。').fontColor(this.palette().muted).fontSize(12).padding({ top: 18, bottom: 18 })
      else ForEach(this.sessions.slice(0, 4), (item: StudySession, index: number) => {
        Row({ space: 10 }) { Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.stopwatch')).fontSize(18).fontColor([this.palette().primary]) }.width(39).height(39).backgroundColor(this.palette().soft).borderRadius(13); Column({ space: 3 }) { Text(item.goal ?? '专注学习').fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Bold).maxLines(1); Text(`${Math.max(1, Math.floor(item.duration_seconds / 60))} 分钟 · ${item.status === 'completed' ? '已完成' : '进行中'}`).fontColor(this.palette().muted).fontSize(10) }.layoutWeight(1).alignItems(HorizontalAlign.Start) }.width('100%').padding({ top: 9, bottom: 9 }).alignItems(VerticalAlign.Center)
        if (index < Math.min(this.sessions.length, 4) - 1) Divider().color(this.palette().line)
      }, (item: StudySession) => item.id)
    }.width('100%').padding(14).backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(20)
  }
  build() {
    Column() {
      SecondaryHeader({ title: '专注大厅', subtitle: '一次只做一件事，让注意力回到当下', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 14 }) {
          this.GuideScene(); this.Setup(); this.PlanPreview(); this.AssistPreview();
          if (this.behaviorReminder.length > 0) Row({ space: 8 }) { SymbolGlyph($r('sys.symbol.bell')).fontSize(17).fontColor([this.palette().primary]); Text(this.behaviorReminder).fontColor(this.palette().text).fontSize(12).layoutWeight(1) }.width('100%').padding(13).backgroundColor(this.palette().soft).borderRadius(17)
          this.Stats(); this.History(); Blank().height(14)
        }.width('100%').padding({ left: 14, right: 14, bottom: 20 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
