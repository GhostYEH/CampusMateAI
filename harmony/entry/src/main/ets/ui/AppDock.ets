import { CampusPalette, darkPalette, lightPalette } from './Theme';
import { MotionDuration, MotionSpec } from './MotionSpec';
import { LiquidGlassDockStyle, liquidGlassDockStyle } from './LiquidGlassDockSpec';

interface DockItem {
  label: string;
  symbol: Resource;
  index: number;
}

@Component
export struct AppDock {
  @Link activeTab: number;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop pendingCount: number = 0;
  onNavigate: (index: number) => void = () => {};

  @State pressedIndex: number = -1;
  @State pressWaveIndex: number = -1;
  @State pressWaveExpanded: boolean = false;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  glassStyle(): LiquidGlassDockStyle {
    return liquidGlassDockStyle(this.darkMode, this.reduceMotion);
  }

  triggerPress(index: number): void {
    this.activeTab = index;
    this.onNavigate(index);
  }

  beginPress(index: number): void {
    this.pressedIndex = index;
    this.pressWaveIndex = index;
    this.pressWaveExpanded = false;
    if (!this.glassStyle().pressWaveEnabled) {
      return;
    }
    setTimeout(() => {
      if (this.pressWaveIndex === index) {
        this.pressWaveExpanded = true;
      }
    }, 16);
  }

  endPress(index: number): void {
    if (this.pressedIndex === index) {
      this.pressedIndex = -1;
    }
    if (!this.glassStyle().pressWaveEnabled) {
      this.pressWaveIndex = -1;
      return;
    }
    setTimeout(() => {
      if (this.pressWaveIndex === index) {
        this.pressWaveIndex = -1;
        this.pressWaveExpanded = false;
      }
    }, this.glassStyle().pressWaveDuration);
  }

  @Builder
  DockItemView(item: DockItem) {
    Stack({ alignContent: Alignment.Center }) {
      if (this.pressWaveIndex === item.index) {
        Circle()
          .width(this.glassStyle().pressWaveEnabled ?
            (this.pressWaveExpanded ? this.glassStyle().pressWaveDiameter : 18) : 52)
          .height(this.glassStyle().pressWaveEnabled ?
            (this.pressWaveExpanded ? this.glassStyle().pressWaveDiameter : 18) : 52)
          .backgroundColor(this.glassStyle().pressWaveColor)
          .opacity(this.glassStyle().pressWaveEnabled ? (this.pressWaveExpanded ? 0.0 : 0.48) : 0.12)
          .border({ width: 1, color: this.glassStyle().highlightColor })
          .animation({ duration: this.glassStyle().pressWaveDuration, curve: Curve.Smooth })
      }
      Column({ space: 3 }) {
        Stack({ alignContent: Alignment.Center }) {
          if (item.index === 3 && this.activeTab === item.index) {
            Image($r('app.media.ph_robot'))
              .width(this.activeTab === item.index ? 24 : 22)
              .height(this.activeTab === item.index ? 24 : 22)
              .objectFit(ImageFit.Contain)
              .scale({
                x: this.activeTab === item.index ? MotionSpec.scale(this.reduceMotion, 1.12) : (this.pressedIndex === item.index ? MotionSpec.scale(this.reduceMotion, 0.85) : 1.0),
                y: this.activeTab === item.index ? MotionSpec.scale(this.reduceMotion, 1.12) : (this.pressedIndex === item.index ? MotionSpec.scale(this.reduceMotion, 0.85) : 1.0)
              })
              .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.STATE), curve: Curve.Smooth })
          } else {
            SymbolGlyph(item.symbol)
              .fontSize(this.activeTab === item.index ? 23 : 21)
              .fontWeight(this.activeTab === item.index ? FontWeight.Bold : FontWeight.Medium)
              .fontColor([this.activeTab === item.index ? this.palette().primary : this.palette().muted])
              .scale({
                x: this.activeTab === item.index ? MotionSpec.scale(this.reduceMotion, 1.12) : (this.pressedIndex === item.index ? MotionSpec.scale(this.reduceMotion, 0.85) : 1.0),
                y: this.activeTab === item.index ? MotionSpec.scale(this.reduceMotion, 1.12) : (this.pressedIndex === item.index ? MotionSpec.scale(this.reduceMotion, 0.85) : 1.0)
              })
              .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.STATE), curve: Curve.Smooth })
          }
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
          .fontSize(10)
          .fontWeight(this.activeTab === item.index ? FontWeight.Bold : FontWeight.Medium)
          .maxLines(1)
          .opacity(this.activeTab === item.index ? 1.0 : 0.82)
      }
      .width('100%')
      .height('100%')
      .justifyContent(FlexAlign.Center)
      .alignItems(HorizontalAlign.Center)
    }
    .layoutWeight(1)
    .height(60)
    .borderRadius(26)
    .backgroundColor(this.activeTab === item.index ? this.glassStyle().selectedSurfaceColor : Color.Transparent)
    .border({
      width: this.activeTab === item.index ? 0.7 : 0,
      color: this.activeTab === item.index ? this.glassStyle().selectedBorderColor : Color.Transparent
    })
    .shadow({
      radius: this.activeTab === item.index ? 8 : 0,
      color: this.activeTab === item.index ? (this.darkMode ? '#3344A8FF' : '#225B68F2') : Color.Transparent,
      offsetY: 2
    })
    .scale({
      x: this.pressedIndex === item.index ? this.glassStyle().pressScale : 1.0,
      y: this.pressedIndex === item.index ? this.glassStyle().pressScale : 1.0
    })
    .clip(true)
    .animation({ duration: this.glassStyle().motionDuration, curve: Curve.Smooth })
    .onTouch((event: TouchEvent) => {
      if (event.type === TouchType.Down) {
        this.beginPress(item.index);
      } else if (event.type === TouchType.Up || event.type === TouchType.Cancel) {
        this.endPress(item.index);
      }
    })
    .onClick(() => this.triggerPress(item.index))
  }

  build() {
    Column() {
      Stack({ alignContent: Alignment.TopStart }) {
        Row()
          .width('100%')
          .height(60)
          .linearGradient({
            angle: 135,
            colors: [
              [this.glassStyle().highlightColor, 0.0],
              ['#12FFFFFF', 0.42],
              [this.darkMode ? '#1844A8FF' : '#145B68F2', 1.0]
            ]
          })
          .opacity(this.darkMode ? 0.38 : 0.52)
          .hitTestBehavior(HitTestMode.None)

        Row() {
          ForEach([
            { label: '首页', symbol: $r('sys.symbol.house'), index: 0 },
            { label: '课程', symbol: $r('sys.symbol.book'), index: 1 },
            { label: '待办', symbol: $r('sys.symbol.checkmark_circle'), index: 2 },
            { label: 'CPM', symbol: $r('sys.symbol.robot'), index: 3 },
            { label: '我的', symbol: $r('sys.symbol.person'), index: 4 }
          ], (item: DockItem) => {
            this.DockItemView(item)
          })
        }
        .width('100%')
        .height(60)

        Row()
          .width('84%')
          .height(1)
          .position({ x: '8%', y: 1 })
          .linearGradient({
            angle: 0,
            colors: [['#00FFFFFF', 0.0], [this.glassStyle().highlightColor, 0.5], ['#00FFFFFF', 1.0]]
          })
          .opacity(0.82)
          .hitTestBehavior(HitTestMode.None)
      }
      .width('100%')
      .height(60)
    }
    .width('100%')
    .height(80)
    .padding({ left: 6, right: 6, top: 8, bottom: 8 })
    .alignItems(HorizontalAlign.Center)
    .backgroundColor(this.glassStyle().surfaceColor)
    .backdropBlur(this.glassStyle().backdropBlur)
    .border({ width: 0.7, color: this.glassStyle().highlightColor })
    .borderRadius(40)
    .shadow({
      radius: 28,
      color: this.glassStyle().shadowColor,
      offsetY: 8
    })
    .margin({ left: 14, right: 14, bottom: 10 })
  }
}
