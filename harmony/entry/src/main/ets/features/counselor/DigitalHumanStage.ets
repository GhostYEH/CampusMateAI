import { webview } from '@kit.ArkWeb';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { CounselorVisualSpec } from './CounselorVisualSpec';

interface PageEndEvent { url: string }

@Component
export struct DigitalHumanStage {
  @Prop apiBaseUrl: string = '';
  @Prop authToken: string = '';
  @Prop speechText: string = '';
  @Prop @Watch('onSpeechRequestChanged') speechRequestId: number = 0;
  @Prop darkMode: boolean = false;
  @State ready: boolean = false;
  @State runtimeRequested: boolean = false;
  @State errorMessage: string = '';
  @State muted: boolean = false;
  @State paused: boolean = false;
  private controller: webview.WebviewController = new webview.WebviewController();
  private lastSpokenRequestId: number = 0;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  stageUrl(): string {
    return CounselorVisualSpec.speechRuntimeUrl(this.apiBaseUrl);
  }

  run(script: string): void {
    if (!this.ready) return;
    this.controller.runJavaScript(script).catch(() => {
      this.errorMessage = '语音连接暂时不可用，文字回答不受影响';
    });
  }

  configure(): void {
    const payload: string = JSON.stringify({ apiBaseUrl: this.apiBaseUrl, accessToken: this.authToken });
    this.run(`window.CampusMateDigitalHuman.configure(${payload});`);
  }

  requestRuntimeIfNeeded(): void {
    if (CounselorVisualSpec.shouldLoadSpeechRuntime(this.speechRequestId, this.speechText)) {
      this.runtimeRequested = true;
    }
  }

  speakIfNeeded(): void {
    if (!this.ready || this.speechRequestId <= 0 || this.speechRequestId === this.lastSpokenRequestId || this.speechText.trim().length === 0) return;
    this.lastSpokenRequestId = this.speechRequestId;
    this.configure();
    this.run(`window.CampusMateDigitalHuman.speak(${JSON.stringify(this.speechText)});`);
  }

  onSpeechRequestChanged(): void {
    this.requestRuntimeIfNeeded();
    this.speakIfNeeded();
  }

  toggleMute(): void {
    this.muted = !this.muted;
    this.run('window.CampusMateDigitalHuman.toggleMuted();');
  }

  togglePause(): void {
    if (!this.ready || this.speechText.trim().length === 0) return;
    this.paused = !this.paused;
    this.run('window.CampusMateDigitalHuman.togglePaused();');
  }

  replaySpeech(): void {
    if (this.speechText.trim().length === 0 || this.muted) return;
    this.requestRuntimeIfNeeded();
    this.run('window.CampusMateDigitalHuman.replay();');
  }

  aboutToAppear(): void {
    this.requestRuntimeIfNeeded();
  }

  aboutToDisappear(): void {
    this.run('window.CampusMateDigitalHuman.stop();');
  }

  @Builder
  Avatar() {
    Stack({ alignContent: Alignment.TopStart }) {
      Stack({ alignContent: Alignment.TopStart }) {
        Image($r('app.media.cpm_avatar'))
          .width(CounselorVisualSpec.AVATAR_IMAGE_WIDTH)
          .height(CounselorVisualSpec.AVATAR_IMAGE_HEIGHT)
          .objectFit(ImageFit.Fill)
          .position({ x: CounselorVisualSpec.AVATAR_IMAGE_X, y: CounselorVisualSpec.AVATAR_IMAGE_Y })
      }
      .width(CounselorVisualSpec.AVATAR_VIEWPORT)
      .height(CounselorVisualSpec.AVATAR_VIEWPORT)
      .backgroundColor(this.darkMode ? '#FF273149' : '#FFE7ECFF')
      .border({ width: 1.5, color: '#F2FFFFFF' })
      .borderRadius(CounselorVisualSpec.AVATAR_VIEWPORT / 2)
      .clip(true)
      .position({ x: 8, y: 0 })

      Stack({ alignContent: Alignment.Center }) {
        Image($r('app.media.ph_sparkle')).width(21).height(21).objectFit(ImageFit.Contain)
      }
      .width(36)
      .height(36)
      .backgroundColor(this.palette().surface)
      .borderRadius(18)
      .shadow({ radius: 10, color: '#244056A6', offsetY: 3 })
      .position({ x: 0, y: 116 })
    }
    .width(160)
    .height(152)
  }

  @Builder
  SpeechRuntime() {
    if (this.runtimeRequested) {
      Web({ src: this.stageUrl(), controller: this.controller })
        .javaScriptAccess(true)
        .domStorageAccess(true)
        .databaseAccess(false)
        .mediaPlayGestureAccess(false)
        .onPageEnd((_event: PageEndEvent) => {
          this.ready = true;
          this.errorMessage = '';
          this.configure();
          if (this.muted) this.run('window.CampusMateDigitalHuman.toggleMuted();');
          this.speakIfNeeded();
        })
        .onErrorReceive(() => {
          this.errorMessage = '语音加载失败，文字聊天仍可使用';
        })
        .width(1)
        .height(1)
        .opacity(0)
        .position({ x: 0, y: 0 })
    }
  }

  @Builder
  ControlButton(label: string, symbol: Resource, action: () => void) {
    Column({ space: 5 }) {
      SymbolGlyph(symbol).fontSize(22).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().text).fontSize(11).fontWeight(FontWeight.Medium)
    }
    .width(50)
    .height(60)
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .backgroundColor(this.darkMode ? '#E6202A40' : '#ECFFFFFF')
    .border({ width: 1, color: this.palette().line })
    .borderRadius(15)
    .onClick(action)
  }

  build() {
    Stack({ alignContent: Alignment.TopStart }) {
      Circle().width(176).height(176).fill(this.darkMode ? '#332C3C66' : '#42E5E9FF').position({ x: 0, y: 34 })
      Circle().width(72).height(72).fill(this.darkMode ? '#221D2A48' : '#36FFFFFF').position({ x: '70%', y: 10 })
      this.SpeechRuntime()

      Row({ space: 5 }) {
        this.Avatar()
        Column({ space: 9 }) {
          Text('你好，我是CPM').fontColor(this.palette().primary).fontSize(22).fontWeight(FontWeight.Bold).maxLines(1)
          Text('尽管提问！').fontColor(this.palette().muted).fontSize(14)
          Row({ space: 6 }) {
            this.ControlButton(this.muted ? '开启' : '静音', $r('sys.symbol.speaker_slash'), () => this.toggleMute())
            this.ControlButton(this.paused ? '继续' : '暂停', $r('sys.symbol.pause_circle'), () => this.togglePause())
            this.ControlButton('重播', $r('sys.symbol.arrow_clockwise'), () => this.replaySpeech())
          }.width('100%')
          if (this.errorMessage.length > 0) {
            Text(this.errorMessage).fontColor(this.palette().muted).fontSize(9).maxLines(1)
          }
        }
        .layoutWeight(1)
        .alignItems(HorizontalAlign.Start)
      }
      .width('100%')
      .padding({ left: 8, right: 10, top: 37 })
      .alignItems(VerticalAlign.Center)
    }
    .width('100%')
    .height(CounselorVisualSpec.HERO_HEIGHT)
    .backgroundColor(this.darkMode ? '#FF1B2436' : '#F7FFFFFF')
    .border({ width: 1.5, color: this.darkMode ? '#FF33405A' : '#E9FFFFFF' })
    .borderRadius(28)
    .shadow({ radius: 20, color: this.darkMode ? '#33000000' : '#184056A6', offsetY: 7 })
    .clip(true)
  }
}
