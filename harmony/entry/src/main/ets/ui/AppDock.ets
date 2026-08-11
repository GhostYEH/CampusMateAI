import { CampusPalette, darkPalette, lightPalette } from './Theme';
import { curves } from '@kit.ArkUI';

interface DockItem {
  label: string;
  symbol: Resource;
  index: number;
}

@Component
export struct AppDock {
  @Prop activeTab: number = 0;
  @Prop darkMode: boolean = false;
  @Prop pendingCount: number = 0;
  onNavigate: (index: number) => void = () => {};

  @State pressedIndex: number = -1;
  @State pressScale: number = 1.0;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  triggerPress(index: number): void {
    this.pressedIndex = index;
    animateTo({ duration: 180, curve: curves.springMotion(0.35, 0.6) }, () => {
      this.pressScale = 0.88;
    });
    setTimeout(() => {
      animateTo({ duration: 420, curve: curves.responsiveSpringMotion(0.55, 0.85) }, () => {
        this.pressScale = 1.0;
      });
    }, 180);
    this.onNavigate(index);
  }

  @Builder
  DockItemView(item: DockItem, isActive: boolean) {
    Column({ space: 3 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(item.symbol)
          .fontSize(isActive ? 23 : 21)
          .fontWeight(isActive ? FontWeight.Bold : FontWeight.Medium)
          .fontColor([isActive ? this.palette().primary : this.palette().muted])
          .scale({
            x: isActive ? 1.1 : (this.pressedIndex === item.index ? this.pressScale : 1.0),
            y: isActive ? 1.1 : (this.pressedIndex === item.index ? this.pressScale : 1.0)
          })
          .animation({ duration: 380, curve: curves.responsiveSpringMotion(0.45, 0.75) })
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
            .scale({ x: isActive ? 1.18 : 1.0, y: isActive ? 1.18 : 1.0 })
            .animation({ duration: 380, curve: curves.responsiveSpringMotion(0.5, 0.8) })
        }
      }
      .width(42)
      .height(26)
      Text(item.label)
        .fontColor(isActive ? this.palette().primary : this.palette().muted)
        .fontSize(item.index === 3 ? 8.5 : 10)
        .fontWeight(isActive ? FontWeight.Bold : FontWeight.Medium)
        .maxLines(1)
        .opacity(isActive ? 1.0 : 0.82)
        .animation({ duration: 280, curve: Curve.EaseInOut })
    }
    .layoutWeight(1)
    .height(60)
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .borderRadius(26)
    .backgroundColor(isActive ? (this.darkMode ? '#269CC7D0' : '#1A5B68F2') : Color.Transparent)
    .scale({
      x: this.pressedIndex === item.index ? this.pressScale : 1.0,
      y: this.pressedIndex === item.index ? this.pressScale : 1.0
    })
    .animation({ duration: 420, curve: curves.responsiveSpringMotion(0.55, 0.85) })
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
        this.DockItemView(item, this.activeTab === item.index)
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
