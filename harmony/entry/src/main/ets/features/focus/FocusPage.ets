import { StudySession, FocusMode } from '../../data/Models';
import { FocusModeMapper } from '../../data/FocusModeMapper';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct FocusPage {
  @Prop sessions: StudySession[] = [];
  @Prop activeSession?: StudySession = undefined;
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @State mode: string = '专注';
  @State secondsLeft: number = 25 * 60;
  @State running: boolean = false;
  @State startPressed: boolean = false;
  private timerId: number = -1;
  onBack: () => void = () => {};
  onStart: (mode: FocusMode) => void = () => {};
  onPause: () => void = () => {};
  onResume: () => void = () => {};
  onFinish: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToDisappear(): void { this.stopClock(); }
  currentFocusMode(): FocusMode { return FocusModeMapper.fromLabel(this.mode); }
  totalSeconds(): number { return this.mode === '专注' ? 25 * 60 : this.mode === '短休息' ? 5 * 60 : 15 * 60; }
  timeText(): string {
    const minute = Math.floor(this.secondsLeft / 60).toString().padStart(2, '0');
    const second = (this.secondsLeft % 60).toString().padStart(2, '0');
    return `${minute}:${second}`;
  }
  stopClock(): void { if (this.timerId >= 0) { clearInterval(this.timerId); this.timerId = -1; } }
  startClock(): void {
    if (this.running) { this.running = false; this.stopClock(); this.onPause(); return; }
    this.stopClock();
    this.running = true;
    if (this.secondsLeft === this.totalSeconds()) this.onStart(this.currentFocusMode()); else this.onResume();
    this.timerId = setInterval(() => {
      if (this.secondsLeft > 0) this.secondsLeft -= 1;
      else { this.running = false; this.stopClock(); this.onFinish(); }
    }, 1000);
  }
  resetMode(mode: string): void { this.stopClock(); this.running = false; this.mode = mode; this.secondsLeft = this.totalSeconds(); }

  @Builder ModeTabs() {
    Row({ space: 7 }) {
      ForEach(['专注','短休息','长休息'], (item: string) => {
        Text(item).layoutWeight(1).textAlign(TextAlign.Center).fontSize(11).padding({ top: 8, bottom: 8 })
          .fontColor(this.mode === item ? '#FFFFFFFF' : this.palette().muted)
          .backgroundColor(this.mode === item ? this.palette().primary : this.palette().surface)
          .border({ width: 1, color: this.mode === item ? this.palette().primary : this.palette().line }).borderRadius(18)
          .animation({ duration: 220, curve: Curve.EaseInOut })
          .onClick(() => this.resetMode(item))
      })
    }.width('100%')
  }

  @Builder TimerCard() {
    Column({ space: 14 }) {
      Stack({ alignContent: Alignment.Center }) {
        Progress({ value: this.totalSeconds() - this.secondsLeft, total: this.totalSeconds(), type: ProgressType.Ring })
          .width(220).height(220).color(this.palette().primary).backgroundColor(this.palette().soft).style({ strokeWidth: 10 })
        Column({ space: 6 }) {
          SymbolGlyph($r('sys.symbol.timer')).fontSize(24).fontColor([this.palette().primary])
          Text(this.timeText()).fontColor(this.palette().primary).fontSize(44).fontWeight(FontWeight.Bold)
          Text(this.running ? '专注进行中' : this.secondsLeft !== this.totalSeconds() ? '已暂停' : '准备开始').fontColor(this.palette().muted).fontSize(11)
        }
      }.width(230).height(230)
      Row({ space: 10 }) {
        Button({ type: ButtonType.Capsule }) {
          Row({ space: 7 }) {
            if (this.running) {
              SymbolGlyph($r('sys.symbol.pause')).fontSize(17).fontColor(['#FFFFFFFF'])
            } else {
              SymbolGlyph($r('sys.symbol.play')).fontSize(17).fontColor(['#FFFFFFFF'])
            }
            Text(this.running ? '暂停' : this.secondsLeft !== this.totalSeconds() ? '继续' : '开始专注').fontColor('#FFFFFFFF').fontSize(13).fontWeight(FontWeight.Bold)
          }
        }.layoutWeight(1).height(48).backgroundColor(this.palette().primary)
          .scale({ x: this.startPressed ? 0.95 : 1.0, y: this.startPressed ? 0.95 : 1.0 })
          .animation({ duration: 150, curve: Curve.EaseOut })
          .onClick(() => { this.startPressed = true; setTimeout(() => { this.startPressed = false; }, 150); this.startClock(); })
        Button('结束').width(92).height(48).backgroundColor(this.palette().soft).fontColor(this.palette().primary)
          .onClick(() => { this.stopClock(); this.running = false; this.secondsLeft = this.totalSeconds(); this.onFinish(); })
      }.width('100%')
    }.width('100%').padding({ top: 20, left: 16, right: 16, bottom: 18 }).backgroundColor(this.palette().surface).borderRadius(22)

  }

  @Builder Record(item: StudySession) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.stopwatch')).fontSize(19).fontColor([this.palette().primary])
      }.width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text(`${item.goal ?? '专注学习'} · ${(item.started_at ?? '').substring(0, Math.min(10, (item.started_at ?? '').length))}`).fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Bold)
        Text(`${Math.max(1, Math.floor((item.duration_seconds ?? 0) / 60))} 分钟 · ${item.status === 'completed' ? '已完成' : '进行中'}`).fontColor(this.palette().muted).fontSize(10)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding({ top: 10, bottom: 10 })
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 12 })).animation({ duration: 280, curve: Curve.EaseOut }))
  }

  build() {
    Column() {
      SecondaryHeader({ title: '专注自习', subtitle: '一次只做一件事，让注意力回到当下', darkMode: this.darkMode, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          this.ModeTabs()
          this.TimerCard()
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(17).fontColor([this.palette().success])
            Column({ space: 2 }) {
              Text('学习状态辅助').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
              Text('鸿蒙端不上传画面，专注记录已真实同步后端').fontColor(this.palette().muted).fontSize(10)
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          }.width('100%').padding(13).backgroundColor(this.palette().surface).borderRadius(16)
          Text('专注记录').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).width('100%')
          Column() {
            if (this.loading) { LoadingProgress().width(32).height(32).color(this.palette().primary).margin(28) }
            else if (this.sessions.length === 0) { Text('还没有专注记录').fontColor(this.palette().muted).fontSize(12).padding(28) }
            else {
              ForEach(this.sessions, (item: StudySession, index: number) => { this.Record(item); if (index < this.sessions.length - 1) { Divider().color(this.palette().line) } }, (item: StudySession) => item.id)
            }
          }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
          Blank().height(18)
        }.width('100%').padding({ left: 14, right: 14, bottom: 20 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
