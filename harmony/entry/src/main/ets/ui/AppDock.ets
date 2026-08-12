import { CampusPalette, darkPalette, lightPalette } from './Theme';

interface DockItem {
  label: string;
  symbol: Resource;
  index: number;
}

@Component
export struct AppDock {
  @Link activeTab: number;
  @Prop darkMode: boolean = false;
  @Prop pendingCount: number = 0;
  onNavigate: (index: number) => void = () => {};

  @State pressedIndex: number = -1;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  triggerPress(index: number): void {
    this.activeTab = index;
    this.pressedIndex = index;
    setTimeout(() => {
      if (this.pressedIndex === index) {
        this.pressedIndex = -1;
      }
    }, 180);
    this.onNavigate(index);
  }

  @Builder
  DockItemView(item: DockItem) {
    Column({ space: 3 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(item.symbol)
          .fontSize(this.activeTab === item.index ? 23 : 21)
          .fontWeight(this.activeTab === item.index ? FontWeight.Bold : FontWeight.Medium)
          .fontColor([this.activeTab === item.index ? this.palette().primary : this.palette().muted])
          .scale({
            x: this.activeTab === item.index ? 1.1 : (this.pressedIndex === item.index ? 0.88 : 1.0),
            y: this.activeTab === item.index ? 1.1 : (this.pressedIndex === item.index ? 0.88 : 1.0)
          })
          .animation({ duration: 180, curve: Curve.EaseOut })
        if (item.index === 2 && this.pendingCount > 0) {
          Text(this.pendingCount > 9 ? '9+' : this.pendingCount.toString())
            .fontColor('#FFFFFFFF')
            .fontSize(8)
            .fontWeight(FontWeight.Bold)
            .textAlign(TextAlign.Center)
            .width(16)
            .height(16)
            .backgroundColor('#FFED6E52')
            .borderRadius(8)
            .position({ x: 22, y: -3 })
        }
      }
      .width(42)
      .height(26)
      Text(item.label)
        .fontColor(this.activeTab === item.index ? this.palette().primary : this.palette().muted)
        .fontSize(item.index === 3 ? 8.5 : 10)
        .fontWeight(this.activeTab === item.index ? FontWeight.Bold : FontWeight.Medium)
        .maxLines(1)
        .opacity(this.activeTab === item.index ? 1.0 : 0.82)
    }
    .layoutWeight(1)
    .height(60)
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .borderRadius(26)
    .backgroundColor(this.activeTab === item.index ? (this.darkMode ? '#269CC7D0' : '#1A5B68F2') : Color.Transparent)
    .scale({
      x: this.pressedIndex === item.index ? 0.94 : 1.0,
      y: this.pressedIndex === item.index ? 0.94 : 1.0
    })
    .animation({ duration: 180, curve: Curve.EaseOut })
    .onClick(() => this.triggerPress(item.index))
  }

  build() {
    Row() {
      ForEach([
        { label: '首页', symbol: $r('sys.symbol.house'), index: 0 },
        { label: '课程', symbol: $r('sys.symbol.book'), index: 1 },
        { label: '待办', symbol: $r('sys.symbol.checkmark_circle'), index: 2 },
        { label: 'AI 校园助手', symbol: $r('sys.symbol.robot'), index: 3 },
        { label: '我的', symbol: $r('sys.symbol.person'), index: 4 }
      ], (item: DockItem) => {
        this.DockItemView(item)
      })
    }
    .width('100%')
    .height(76)
    .padding({ left: 6, right: 6, top: 8, bottom: 8 })
    .alignItems(VerticalAlign.Center)
    .backgroundColor(this.darkMode ? '#CC0E1F26' : '#DDF6F8FA')
    .backdropBlur(32)
    .border({ width: 0.5, color: this.darkMode ? '#33FFFFFF' : '#22FFFFFF' })
    .borderRadius(40)
    .shadow({
      radius: 28,
      color: this.darkMode ? '#80000000' : '#1A0B1830',
      offsetY: 8
    })
    .margin({ left: 14, right: 14, bottom: 10 })
  }
}
