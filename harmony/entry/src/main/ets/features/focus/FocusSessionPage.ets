import { ChatMessage, FocusMode, StudySession } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';
import { FocusPresentationState } from './FocusPresentationState';
import { FocusDisplayMode, FocusSceneId, FocusSceneOption, FocusSceneState } from './FocusSceneState';
import { FocusSessionMode } from './FocusPage';
import { FocusSessionState } from './FocusSessionState';
import { FocusRobot } from './FocusRobot';
import { FocusVoiceState } from './FocusVoiceState';

@Component
export struct FocusSessionPage {
  @Prop session?: StudySession = undefined;
  @Prop plannedSeconds: number = 1500;
  @Prop sessionMode: FocusSessionMode = 'QUIET';
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop assistDetail: string = '';
  @Prop assistLabel: string = '';
  @Prop assistConfidence: number = 0;
  @Prop messages: ChatMessage[] = [];
  @Prop sending: boolean = false;
  @Prop voiceState: FocusVoiceState = { phase: 'IDLE', message: '点击麦克风，和 CampusMate 实时对话', transcript: '', answer: '' };
  @Prop hasPlanStep: boolean = false;
  @Link input: string;
  @State secondsLeft: number = 1500;
  @State showChat: boolean = false;
  @State actionPending: boolean = false;
  @State showFinishChoice: boolean = false;
  @State displayMode: FocusDisplayMode = FocusSceneState.defaultDisplayMode();
  @State selectedScene: FocusSceneId = 'RAINY_ROOM';
  private timerId: number = -1;
  onBack: () => void = () => {};
  onPause: () => Promise<boolean> = async () => false;
  onResume: () => Promise<boolean> = async () => false;
  onFinish: (completePlanStep: boolean) => Promise<boolean> = async (_completePlanStep: boolean) => false;
  onVoiceToggle: () => Promise<void> = async () => {};
  onVoiceInterrupt: () => Promise<void> = async () => {};
  onSend: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  glassSurface(): string { return this.palette().glass.surface; }
  glassBorder(): string { return this.palette().glass.border; }
  glassShadow(): string { return this.palette().glass.shadow; }
  glassBlur(): number { return this.palette().glass.backdropBlur + (this.displayMode === 'IMMERSIVE' ? 6 : 0); }
  aboutToAppear(): void {
    this.secondsLeft = this.session === undefined ? this.plannedSeconds :
      FocusSessionState.remainingSeconds(this.session, Date.now(), this.plannedSeconds);
    this.syncClock();
  }
  aboutToDisappear(): void { this.stopClock(); }
  isPaused(): boolean { return this.session?.status === 'paused'; }
  totalSeconds(): number { return Math.max(1, this.session?.planned_duration_seconds ?? this.plannedSeconds); }
  stopClock(): void { if (this.timerId >= 0) { clearInterval(this.timerId); this.timerId = -1; } }
  syncClock(force: boolean = false): void {
    this.stopClock();
    if (!force && this.isPaused()) return;
    this.timerId = setInterval(() => {
      if (this.session !== undefined) {
        this.secondsLeft = FocusSessionState.remainingSeconds(this.session, Date.now(), this.plannedSeconds);
      } else if (this.secondsLeft > 1) {
        this.secondsLeft -= 1;
      }
      if (this.secondsLeft <= 0) { this.secondsLeft = 0; this.stopClock(); this.finishSession(); }
    }, 1000);
  }
  timeText(): string {
    const minute = Math.floor(this.secondsLeft / 60).toString().padStart(2, '0');
    return `${minute}:${(this.secondsLeft % 60).toString().padStart(2, '0')}`;
  }
  guideStatus(): string {
    if (this.sending) return '让我想想';
    if (this.sessionMode === 'SMART_GUARD') return '我在留意你的学习节奏';
    if (this.sessionMode === 'AI_COMPANION') return '我会陪你完成这段专注';
    return '安静地陪你专注';
  }
  async togglePause(): Promise<void> {
    if (this.actionPending) return;
    this.actionPending = true;
    try {
      if (this.isPaused()) {
        if (await this.onResume()) this.syncClock(true);
      } else {
        this.stopClock();
        if (!await this.onPause()) this.syncClock(true);
      }
    } finally {
      this.actionPending = false;
    }
  }
  async finishSession(): Promise<void> {
    if (this.actionPending) return;
    if (this.hasPlanStep) { this.showFinishChoice = true; return; }
    await this.finishSessionWithPlan(true);
  }
  async finishSessionWithPlan(completePlanStep: boolean): Promise<void> {
    this.showFinishChoice = false;
    if (this.actionPending) return;
    this.actionPending = true;
    this.stopClock();
    try {
      const finished: boolean = await this.onFinish(completePlanStep);
      if (!finished && !this.isPaused()) this.syncClock(true);
    } finally {
      this.actionPending = false;
    }
  }

  @Builder Guide() {
    Stack({ alignContent: Alignment.Center }) {
      Circle().width(132).height(132).fill(this.darkMode ? '#FF243A65' : '#FFF2F4FF')
      Circle().width(102).height(102).fill(this.palette().soft)
      FocusRobot({ state: FocusPresentationState.robotStateForVoice(this.voiceState.phase === 'IDLE' ? (this.sending ? 'THINKING' : 'IDLE') : this.voiceState.phase), darkMode: this.darkMode, reduceMotion: this.reduceMotion })
      if (this.sending) Text('…').fontSize(32).fontWeight(FontWeight.Bold).fontColor(this.palette().primary).position({ x: '71%', y: '8%' })
    }.width(132).height(132)
  }
  @Builder VoiceBar() {
    Column({ space: 7 }) {
      Row({ space: 8 }) {
        Stack({ alignContent: Alignment.Center }) {
          SymbolGlyph(this.voiceState.phase === 'IDLE' || this.voiceState.phase === 'ERROR' ? $r('sys.symbol.mic') : $r('sys.symbol.xmark')).fontSize(18).fontColor(['#FFFFFFFF'])
        }.width(40).height(40).backgroundColor(this.voiceState.phase === 'ERROR' ? this.palette().danger : this.palette().primary).borderRadius(20)
          .onClick(() => this.onVoiceToggle())
        Column({ space: 2 }) {
          Text(this.voiceState.phase === 'IDLE' ? '实时语音陪伴' : this.voiceState.message).fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Bold)
          Text(this.voiceState.phase === 'ERROR' ? '点按重试，语音只在本机采集并加密传输' : '16 kHz PCM · 全双工对话').fontColor(this.palette().muted).fontSize(10)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        if (this.voiceState.phase === 'SPEAKING') SymbolGlyph($r('sys.symbol.pause_circle')).fontSize(20).fontColor([this.palette().primary]).onClick(() => this.onVoiceInterrupt())
      }.width('100%').alignItems(VerticalAlign.Center)
      if (this.voiceState.transcript.length > 0) Text(`我：${this.voiceState.transcript}`).fontColor(this.palette().muted).fontSize(11).maxLines(2).width('100%')
      if (this.voiceState.answer.length > 0) Text(`CampusMate：${this.voiceState.answer}`).fontColor(this.palette().text).fontSize(11).lineHeight(16).maxLines(3).width('100%')
    }.width('100%').padding(12).backgroundColor(this.glassSurface()).backdropBlur(this.glassBlur()).border({ width: 1, color: this.glassBorder() }).borderRadius(18).shadow({ radius: 18, color: this.glassShadow(), offsetY: 5 })
  }
  @Builder FinishChoice() {
    if (this.showFinishChoice) {
      Column({ space: 10 }) {
        Text('结束这段专注？').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold)
        Text('可以把当前任务步骤标记为完成，也可以只记录本次专注。').fontColor(this.palette().muted).fontSize(11).lineHeight(17)
        Row({ space: 8 }) {
          Button('完成步骤并结束').layoutWeight(1).height(44).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(16).onClick(() => this.finishSessionWithPlan(true))
          Button('仅结束专注').layoutWeight(1).height(44).backgroundColor(this.palette().soft).fontColor(this.palette().primary).borderRadius(16).onClick(() => this.finishSessionWithPlan(false))
        }.width('100%')
        Button('继续专注').width('100%').height(40).backgroundColor(this.palette().background).fontColor(this.palette().muted).borderRadius(14).onClick(() => this.showFinishChoice = false)
      }.width('100%').padding(14).backgroundColor(this.glassSurface()).backdropBlur(this.glassBlur()).border({ width: 1, color: this.glassBorder() }).borderRadius(20).shadow({ radius: 20, color: this.glassShadow(), offsetY: 6 }).position({ bottom: 18 })
    }
  }
  @Builder Timer() {
    Stack({ alignContent: Alignment.Center }) {
      Progress({ value: this.totalSeconds() - this.secondsLeft, total: this.totalSeconds(), type: ProgressType.Ring }).width(238).height(238).color(this.palette().primary).backgroundColor(this.palette().soft).style({ strokeWidth: 11 })
      Column({ space: 5 }) {
        SymbolGlyph($r('sys.symbol.timer')).fontSize(22).fontColor([this.palette().primary])
        Text(this.timeText()).fontColor(this.palette().text).fontSize(43).fontWeight(FontWeight.Bold)
        Text(this.isPaused() ? '已暂停' : '专注进行中').fontColor(this.palette().muted).fontSize(12)
      }.alignItems(HorizontalAlign.Center)
    }.width(244).height(244).padding(10).backgroundColor(this.glassSurface()).backdropBlur(this.glassBlur()).border({ width: 1, color: this.glassBorder() }).borderRadius(32).shadow({ radius: 24, color: this.glassShadow(), offsetY: 7 })
  }
  @Builder SensingCard() {
    Column({ space: 7 }) {
      Row() {
        Row({ space: 6 }) { SymbolGlyph($r('sys.symbol.eye')).fontSize(16).fontColor([this.sessionMode === 'SMART_GUARD' ? this.palette().success : this.palette().muted]); Text('学习状态辅助').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold) }.alignItems(VerticalAlign.Center)
        Blank(); Text(this.sessionMode === 'SMART_GUARD' ? '本地运行中' : '暂未开启').fontColor(this.palette().muted).fontSize(10)
      }.width('100%')
      Text(this.sessionMode === 'SMART_GUARD' ? this.assistDetail : '选择智能监督后，系统会在设备本地辅助观察学习状态。').fontColor(this.palette().muted).fontSize(11).lineHeight(17)
      if (this.sessionMode === 'SMART_GUARD' && this.assistLabel.length > 0) Text(`${this.assistLabel} · ${Math.round(this.assistConfidence * 100)}%`).fontColor(this.palette().primary).fontSize(11).fontWeight(FontWeight.Bold)
    }.width('100%').padding(14).backgroundColor(this.glassSurface()).backdropBlur(this.glassBlur()).border({ width: 1, color: this.glassBorder() }).borderRadius(19).shadow({ radius: 18, color: this.glassShadow(), offsetY: 5 })
  }
  @Builder ChatOverlay() {
    if (this.showChat) {
      Column({ space: 10 }) {
        Row() { Text('和 CampusMate 说说').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold); Blank(); SymbolGlyph($r('sys.symbol.xmark')).fontSize(17).fontColor([this.palette().muted]).onClick(() => this.showChat = false) }.width('100%')
        if (this.messages.length === 0) Text('需要时可以说说你的困惑、下一步，或请我帮你重新聚焦。').fontColor(this.palette().muted).fontSize(12).lineHeight(18)
        else ForEach(this.messages.slice(-3), (message: ChatMessage) => { Text(`${message.role === 'assistant' ? 'CampusMate' : '我'}：${message.content}`).fontColor(message.role === 'assistant' ? this.palette().text : this.palette().primary).fontSize(12).lineHeight(18) }, (message: ChatMessage) => message.id)
        Row({ space: 8 }) {
          TextInput({ text: this.input, placeholder: '输入一句话…' }).layoutWeight(1).height(44).fontColor(this.palette().text).placeholderColor(this.palette().muted).backgroundColor(this.palette().background).border({ width: 1, color: this.palette().glass.border }).borderRadius(16).onChange((value: string) => this.input = value).onSubmit(() => { if (!this.sending && this.input.trim().length > 0) this.onSend(); })
          Stack({ alignContent: Alignment.Center }) { if (this.sending) LoadingProgress().width(17).height(17).color('#FFFFFFFF'); else SymbolGlyph($r('sys.symbol.paperplane_fill')).fontSize(18).fontColor(['#FFFFFFFF']) }.width(44).height(44).backgroundColor(this.palette().primary).borderRadius(22).onClick(() => { if (!this.sending && this.input.trim().length > 0) this.onSend(); })
        }.width('100%').alignItems(VerticalAlign.Center)
        Text('文字和实时语音共用同一位 CampusMate 陪伴。').fontColor(this.palette().muted).fontSize(10)
      }.width('100%').padding(14).backgroundColor(this.glassSurface()).backdropBlur(this.glassBlur()).border({ width: 1, color: this.glassBorder() }).borderRadius(20).shadow({ radius: 20, color: this.glassShadow(), offsetY: 6 }).transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 12) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.STATE), curve: Curve.EaseOut }))
    }
  }
  @Builder SceneBackdrop() {
    if (this.selectedScene === 'QUIET_LIBRARY') {
      Image($r('app.media.focus_scene_quiet_library')).width('100%').height('100%').objectFit(ImageFit.Cover)
    } else if (this.selectedScene === 'FOREST_MORNING') {
      Image($r('app.media.focus_scene_forest_morning')).width('100%').height('100%').objectFit(ImageFit.Cover)
    } else {
      Image($r('app.media.focus_scene_rainy_room')).width('100%').height('100%').objectFit(ImageFit.Cover)
    }
    Column() {}.width('100%').height('100%').linearGradient({ angle: 180, colors: this.darkMode ? [['#99243B59', 0], ['#1113263A', 0.35], ['#D9000000', 1]] : [['#553B5575', 0], ['#11000000', 0.5], ['#A6000000', 1]] })
  }
  @Builder SceneTools() {
    Column({ space: 8 }) {
      Row({ space: 8 }) {
        SymbolGlyph($r('sys.symbol.star_fill')).fontSize(17).fontColor([this.palette().primary])
        Column({ space: 2 }) { Text(FocusSceneState.scene(this.selectedScene).title).fontColor('#FFFFFFFF').fontSize(13).fontWeight(FontWeight.Bold); Text('选择一个适合当下的专注场景').fontColor('#D9FFFFFF').fontSize(10) }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        Text(this.displayMode === 'IMMERSIVE' ? '专注空间' : '普通模式').fontColor('#FFFFFFFF').fontSize(11).fontWeight(FontWeight.Bold).padding({ left: 9, right: 9, top: 6, bottom: 6 }).backgroundColor('#3AFFFFFF').borderRadius(12).onClick(() => { this.displayMode = FocusSceneState.toggleDisplayMode(this.displayMode); })
      }.width('100%').alignItems(VerticalAlign.Center)
      Row({ space: 6 }) {
        ForEach(FocusSceneState.scenes(), (scene: FocusSceneOption) => {
          Text(scene.title).fontColor(scene.id === this.selectedScene ? this.palette().primary : '#E6FFFFFF').fontSize(10).fontWeight(FontWeight.Bold).layoutWeight(1).textAlign(TextAlign.Center).padding({ top: 7, bottom: 7 }).backgroundColor(scene.id === this.selectedScene ? '#EEFFFFFF' : '#2EFFFFFF').borderRadius(12).onClick(() => { this.selectedScene = scene.id; })
        }, (scene: FocusSceneOption) => scene.id)
      }.width('100%')
    }.width('100%').padding(12).backgroundColor(this.glassSurface()).backdropBlur(this.glassBlur()).border({ width: 1, color: this.glassBorder() }).borderRadius(22).shadow({ radius: 20, color: this.glassShadow(), offsetY: 7 })
  }
  build() {
    Stack() {
      if (this.displayMode === 'IMMERSIVE') this.SceneBackdrop()
      Column({ space: 12 }) {
        Row() { SymbolGlyph($r('sys.symbol.arrow_left')).fontSize(20).fontColor([this.displayMode === 'IMMERSIVE' ? '#FFFFFFFF' : this.palette().text]).onClick(() => this.onBack()); Blank(); Text(this.displayMode === 'IMMERSIVE' ? '专注空间' : '普通模式').fontColor(this.displayMode === 'IMMERSIVE' ? '#FFFFFFFF' : this.palette().text).fontSize(16).fontWeight(FontWeight.Bold); Blank(); Text(this.displayMode === 'IMMERSIVE' ? '普通模式' : '专注空间').fontColor(this.displayMode === 'IMMERSIVE' ? '#FFFFFFFF' : this.palette().primary).fontSize(11).fontWeight(FontWeight.Bold).padding({ left: 8, right: 8, top: 6, bottom: 6 }).backgroundColor(this.displayMode === 'IMMERSIVE' ? '#3AFFFFFF' : this.palette().soft).borderRadius(12).onClick(() => { this.displayMode = FocusSceneState.toggleDisplayMode(this.displayMode); }); SymbolGlyph($r('sys.symbol.message')).fontSize(20).fontColor([this.displayMode === 'IMMERSIVE' ? '#FFFFFFFF' : this.palette().primary]).margin({ left: 8 }).onClick(() => this.showChat = !this.showChat) }.width('100%').padding({ left: 18, right: 18, top: 18 })
        if (this.displayMode === 'IMMERSIVE') this.SceneTools()
        Scroll() {
          Column({ space: 14 }) {
            this.Guide(); Text(this.voiceState.phase === 'IDLE' ? this.guideStatus() : this.voiceState.message).fontColor(this.displayMode === 'IMMERSIVE' ? '#E6FFFFFF' : this.palette().muted).fontSize(13).width('100%').textAlign(TextAlign.Center)
            this.Timer();
            Row({ space: 10 }) {
              Button(this.isPaused() ? '继续' : '暂停').layoutWeight(1).height(50)
                .backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(19)
                .enabled(!this.actionPending).onClick(() => this.togglePause())
              Button('结束').layoutWeight(1).height(50).backgroundColor(this.palette().soft)
                .fontColor(this.palette().primary).borderRadius(19).enabled(!this.actionPending)
                .onClick(() => this.finishSession())
            }.width('100%')
            this.VoiceBar(); this.SensingCard(); this.ChatOverlay(); Blank().height(4)
          }.width('100%').padding({ left: 18, right: 18, bottom: 22 }).alignItems(HorizontalAlign.Center)
        }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
      }.width('100%').height('100%').backgroundColor(this.displayMode === 'IMMERSIVE' ? '#33000000' : this.palette().background)
      this.FinishChoice()
    }.width('100%').height('100%').backgroundColor(this.displayMode === 'IMMERSIVE' ? '#FF0B1825' : this.palette().background)
  }
}
