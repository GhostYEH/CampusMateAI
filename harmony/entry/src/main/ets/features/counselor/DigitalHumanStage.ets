import { webview } from '@kit.ArkWeb';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

interface PageEndEvent { url: string }

@Component
export struct DigitalHumanStage {
  @Prop apiBaseUrl: string = '';
  @Prop authToken: string = '';
  @Prop speechText: string = '';
  @Prop @Watch('onSpeechRequestChanged') speechRequestId: number = 0;
  @Prop darkMode: boolean = false;
  @Prop stageHeight: number = 470;
  @Prop @Watch('onCommandChanged') command: string = '';
  @Prop @Watch('onCommandChanged') commandRequestId: number = 0;
  @State ready: boolean = false;
  @State errorMessage: string = '';
  private controller: webview.WebviewController = new webview.WebviewController();
  private lastSpokenRequestId: number = 0;
  private lastCommandRequestId: number = 0;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  stageUrl(): string {
    const normalized = this.apiBaseUrl.replace(/\/+$/, '').replace(/\/api\/v1$/, '');
    return `${normalized}/digital-human/mobile.html?embed=1`;
  }

  run(script: string): void {
    this.controller.runJavaScript(script).catch(() => {
      this.errorMessage = '数字人连接暂时不可用，文字回答不受影响';
    });
  }

  configure(): void {
    const payload = JSON.stringify({ apiBaseUrl: this.apiBaseUrl, accessToken: this.authToken });
    this.run(`window.CampusMateDigitalHuman.configure(${payload});`);
  }

  speakIfNeeded(): void {
    if (!this.ready || this.speechRequestId <= 0 || this.speechRequestId === this.lastSpokenRequestId || this.speechText.trim().length === 0) return;
    this.lastSpokenRequestId = this.speechRequestId;
    this.configure();
    this.run(`window.CampusMateDigitalHuman.speak(${JSON.stringify(this.speechText)});`);
  }

  onSpeechRequestChanged(): void {
    this.speakIfNeeded();
  }

  onCommandChanged(): void {
    if (!this.ready || this.commandRequestId <= 0 || this.commandRequestId === this.lastCommandRequestId) return;
    const scripts: Record<string, string> = {
      mute: 'window.CampusMateDigitalHuman.toggleMuted();',
      pause: 'window.CampusMateDigitalHuman.togglePaused();',
      replay: 'window.CampusMateDigitalHuman.replay();'
    };
    const script = scripts[this.command];
    if (script !== undefined) {
      this.lastCommandRequestId = this.commandRequestId;
      this.run(script);
    }
  }

  aboutToDisappear(): void {
    if (this.ready) this.run('window.CampusMateDigitalHuman.stop();');
  }

  build() {
    Stack({ alignContent: Alignment.Center }) {
      Web({ src: this.stageUrl(), controller: this.controller })
        .javaScriptAccess(true)
        .domStorageAccess(true)
        .databaseAccess(true)
        .mediaPlayGestureAccess(false)
        .onPageEnd((_event: PageEndEvent) => {
          this.ready = true;
          this.errorMessage = '';
          this.configure();
          this.speakIfNeeded();
          this.onCommandChanged();
        })
        .onErrorReceive(() => {
          this.errorMessage = '数字人画面加载失败，文字聊天仍可使用';
        })
        .width('100%')
        .height('100%')

      if (!this.ready && this.errorMessage.length === 0) {
        Column({ space: 10 }) {
          LoadingProgress().width(30).height(30).color(this.palette().primary)
          Text('正在唤醒数字人…').fontColor(this.palette().muted).fontSize(12)
        }
      }

      if (this.errorMessage.length > 0) {
        Text(this.errorMessage).fontColor(this.palette().muted).fontSize(12).textAlign(TextAlign.Center)
          .padding(18).backgroundColor(this.palette().surface).borderRadius(14)
      }
    }
    .width('100%')
    .height(this.stageHeight)
    .backgroundColor(this.darkMode ? '#FF1B2436' : '#FFE8EDFB')
    .border({ width: 1, color: this.palette().line })
    .borderRadius(25)
    .clip(true)
  }
}
