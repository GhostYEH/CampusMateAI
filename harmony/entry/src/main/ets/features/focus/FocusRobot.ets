import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { FocusPresentationState, FocusRobotState } from './FocusPresentationState';

@Component
export struct FocusRobot {
  @Prop state: FocusRobotState = 'IDLE';
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop compact: boolean = false;
  @State floatOffset: number = 0;
  @State eyeOpen: boolean = true;
  private pulseTimer: number = -1;

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  robotSize(): number { return this.compact ? 112 : 162; }
  aboutToAppear(): void {
    if (this.reduceMotion) return;
    this.pulseTimer = setInterval((): void => {
      this.floatOffset = this.floatOffset === 0 ? -5 : 0;
      this.eyeOpen = !this.eyeOpen;
    }, 1400);
  }
  aboutToDisappear(): void {
    if (this.pulseTimer >= 0) clearInterval(this.pulseTimer);
    this.pulseTimer = -1;
  }

  @Builder StatusEffect() {
    if (this.state === 'LISTENING') {
      Row({ space: 3 }) {
        ForEach([10, 20, 14], (height: number) => {
          Column().width(3).height(height).backgroundColor('#FF70E5F8').borderRadius(2)
        }, (height: number): string => height.toString())
      }.padding(7).backgroundColor('#D91A2C52').borderRadius(14)
    } else if (this.state === 'THINKING') {
      Text('…').fontSize(this.compact ? 18 : 26).fontWeight(FontWeight.Bold).fontColor(this.palette().primary)
        .padding({ left: 9, right: 9, top: 1, bottom: 3 }).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).border({ width: 1, color: this.palette().primary }).borderRadius(18)
    } else if (this.state === 'SPEAKING') {
      SymbolGlyph($r('sys.symbol.waveform')).fontSize(this.compact ? 20 : 27).fontColor([this.palette().primary])
        .padding(7).backgroundColor(this.palette().soft).borderRadius(18)
    } else if (this.state === 'HAPPY') {
      Text('✦').fontSize(this.compact ? 22 : 30).fontColor('#FFFFD76A')
    }
  }

  build() {
    Stack({ alignContent: Alignment.Center }) {
      Circle().width(this.robotSize() + 26).height(this.robotSize() + 26).fill(this.darkMode ? '#3D9CC7D0' : '#40FFFFFF')
      Image($r('app.media.ai_campus_robot')).width(this.robotSize()).height(this.robotSize()).objectFit(ImageFit.Contain)
        .translate({ y: this.floatOffset }).opacity(this.state === 'ERROR' ? 0.58 : 1)
        .animation({ duration: this.reduceMotion ? 0 : 600, curve: Curve.EaseInOut })
      if (!this.eyeOpen && !this.reduceMotion) {
        Row({ space: this.compact ? 18 : 27 }) {
          Column().width(this.compact ? 9 : 11).height(3).backgroundColor('#FF70E5F8').borderRadius(2)
          Column().width(this.compact ? 9 : 11).height(3).backgroundColor('#FF70E5F8').borderRadius(2)
        }.margin({ top: this.compact ? -6 : -8 })
      }
      Stack() { this.StatusEffect() }.width(44).height(38)
        .position({ x: this.compact ? '72%' : '74%', y: this.compact ? '6%' : '3%' })
    }.width(this.robotSize() + 26).height(this.robotSize() + 26)
  }
}
