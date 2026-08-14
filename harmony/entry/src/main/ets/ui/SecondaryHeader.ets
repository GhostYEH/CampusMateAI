import { CampusPalette, darkPalette, lightPalette } from './Theme';

@Component
export struct SecondaryHeader {
  @Prop title: string = '';
  @Prop subtitle: string = '';
  @Prop darkMode: boolean = false;
  @BuilderParam rightContent: () => void;
  onBack: () => void = () => {};
  @State backPressed: boolean = false;

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  triggerBack(): void {
    this.backPressed = true;
    setTimeout(() => { this.backPressed = false; }, 160);
    this.onBack();
  }

  build() {
    Row({ space: 12 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.arrow_left')).fontSize(21).fontColor([this.palette().text])
      }
      .width(40).height(40).backgroundColor(this.palette().surface).borderRadius(20)
      .border({ width: 1, color: this.palette().line })
      .scale({ x: this.backPressed ? 0.88 : 1.0, y: this.backPressed ? 0.88 : 1.0 })
      .animation({ duration: 160, curve: Curve.EaseOut })
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
