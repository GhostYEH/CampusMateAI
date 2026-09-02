import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { FocusPresentationState } from './FocusPresentationState';

@Component
export struct FocusSummaryPage {
  @Prop actualSeconds: number = 0;
  @Prop interactionCount: number = 0;
  @Prop observation: string = '本次未启用学习状态辅助。';
  @Prop darkMode: boolean = false;
  onReturnHome: () => void = () => {};
  onStartNext: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  @Builder Note(symbol: Resource, title: string, content: string) {
    Row({ space: 10 }) { Stack({ alignContent: Alignment.Center }) { SymbolGlyph(symbol).fontSize(18).fontColor([this.palette().primary]) }.width(38).height(38).backgroundColor(this.palette().soft).borderRadius(19); Column({ space: 4 }) { Text(title).fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold); Text(content).fontColor(this.palette().muted).fontSize(12).lineHeight(18) }.layoutWeight(1).alignItems(HorizontalAlign.Start) }.width('100%').padding(14).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).border({ width: 1, color: this.palette().glass.border }).borderRadius(19).alignItems(VerticalAlign.Top)
  }
  build() {
    Column({ space: 15 }) {
      Stack({ alignContent: Alignment.Center }) { Circle().width(76).height(76).fill(this.palette().soft); SymbolGlyph($r('sys.symbol.checkmark_circle_fill')).fontSize(39).fontColor([this.palette().primary]) }.width(76).height(76).margin({ top: 48 })
      Text('本次专注总结').fontColor(this.palette().text).fontSize(27).fontWeight(FontWeight.Bold)
      Text('CampusMate 已为你整理这段学习').fontColor(this.palette().muted).fontSize(13)
      Column({ space: 6 }) { Text(FocusPresentationState.formatDuration(this.actualSeconds)).fontColor(this.palette().text).fontSize(35).fontWeight(FontWeight.Bold); Text('本次专注 · 已完成').fontColor(this.palette().primary).fontSize(13).fontWeight(FontWeight.Bold) }.width('100%').padding(20).backgroundColor(this.palette().soft).borderRadius(25).alignItems(HorizontalAlign.Center)
      this.Note($r('sys.symbol.message'), 'AI 交流', `本次共交流 ${this.interactionCount} 次。`)
      this.Note($r('sys.symbol.eye'), '学习状态', this.observation)
      Blank().layoutWeight(1)
      Button('开始下一次专注').width('100%').height(53).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(19).onClick(() => this.onStartNext())
      Button('返回专注大厅').width('100%').height(52).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).fontColor(this.palette().primary).border({ width: 1, color: this.palette().glass.border }).borderRadius(19).onClick(() => this.onReturnHome())
    }.width('100%').height('100%').padding({ left: 20, right: 20, bottom: 24 }).alignItems(HorizontalAlign.Center).backgroundColor(this.palette().background)
  }
}
