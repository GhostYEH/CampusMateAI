import { CampusPalette, darkPalette, lightPalette } from './Theme';

@Component
export struct SecondaryHeader {
  @Prop title: string = '';
  @Prop subtitle: string = '';
  @Prop darkMode: boolean = false;
  onBack: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  build() {
    Row({ space: 12 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.arrow_left')).fontSize(21).fontColor([this.palette().text])
      }
      .width(40).height(40).backgroundColor(this.palette().surface).borderRadius(20)
      .border({ width: 1, color: this.palette().line }).onClick(() => this.onBack())

      Column({ space: 3 }) {
        Text(this.title).fontColor(this.palette().text).fontSize(25).fontWeight(FontWeight.Bold)
        if (this.subtitle.length > 0) {
          Text(this.subtitle).fontColor(this.palette().muted).fontSize(11).maxLines(1)
        }
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding({ left: 14, right: 14, top: 12, bottom: 10 }).alignItems(VerticalAlign.Center)
  }
}
