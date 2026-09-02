import { CampusPalette, darkPalette, lightPalette } from './Theme';
import { MotionDuration, MotionSpec } from './MotionSpec';

@Component
export struct SecondaryHeader {
  @Prop title: string = '';
  @Prop subtitle: string = '';
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @BuilderParam rightContent: () => void;
  onBack: () => void = () => {};
  @State backPressed: boolean = false;

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  triggerBack(): void {
    this.backPressed = true;
    setTimeout(() => { this.backPressed = false; }, MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS));
    this.onBack();
  }

  build() {
    Row({ space: 12 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.arrow_left')).fontSize(21).fontColor([this.palette().text])
      }
      .width(40).height(40).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(20)
      .border({ width: 1, color: this.palette().glass.border })
      .scale({ x: this.backPressed ? MotionSpec.scale(this.reduceMotion, 0.90) : 1.0, y: this.backPressed ? MotionSpec.scale(this.reduceMotion, 0.90) : 1.0 })
      .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.PRESS), curve: Curve.EaseOut })
      .onClick(() => this.triggerBack())

      Column({ space: 3 }) {
        Text(this.title).fontColor(this.palette().text).fontSize(25).fontWeight(FontWeight.Bold)
        if (this.subtitle.length > 0) {
          Text(this.subtitle).fontColor(this.palette().muted).fontSize(11).maxLines(1)
        }
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)

      if (this.rightContent) {
        this.rightContent()
      }
    }.width('100%').padding({ left: 14, right: 14, top: 12, bottom: 10 }).alignItems(VerticalAlign.Center)
  }
}
