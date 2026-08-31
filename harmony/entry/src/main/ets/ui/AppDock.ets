import { CampusPalette, darkPalette, lightPalette } from './Theme';
import { MotionDuration, MotionSpec } from './MotionSpec';
import { clampDockDragOffset, dockDragTargetIndex } from './LiquidGlassDockDrag';
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

  @State clickGlowIndex: number = -1;
  @State clickGlowExpanded: boolean = false;
  @State dockWidth: number = 0;
  @State dragOffset: number = 0;
  @State dragging: boolean = false;
  @State dragAccepted: boolean = false;
  @State suppressClick: boolean = false;

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  glassStyle(): LiquidGlassDockStyle {
    return liquidGlassDockStyle(this.darkMode, this.reduceMotion);
  }

  triggerPress(index: number): void {
    if (this.suppressClick) {
      return;
    }
    this.activeTab = index;
    this.onNavigate(index);
  }

  itemWidth(): number {
    return this.dockWidth > 0 ? this.dockWidth / 5 : 0;
  }

  visualTab(): number {
    return this.dragging ?
      dockDragTargetIndex(this.activeTab, this.dragOffset, this.itemWidth(), 5) : this.activeTab;
  }

  isVisualTab(index: number): boolean {
    return this.visualTab() === index;
  }

  beginDrag(index: number): void {
    this.dragAccepted = this.itemWidth() > 0 && index === this.activeTab;
    this.dragging = this.dragAccepted;
    this.dragOffset = 0;
  }

  updateDrag(event: GestureEvent): void {
    if (!this.dragAccepted) return;
    this.dragOffset = clampDockDragOffset(this.activeTab, 5, this.itemWidth(), event.offsetX);
  }

  finishDrag(): void {
    if (!this.dragAccepted) return;
    const source: number = this.activeTab;
    const target: number = dockDragTargetIndex(source, this.dragOffset, this.itemWidth(), 5);
    this.suppressClick = true;
    this.dragAccepted = false;
    this.dragging = false;
    this.activeTab = target;
    this.dragOffset = 0;
    if (target !== source) {
      this.onNavigate(target);
    }
    setTimeout(() => {
      this.suppressClick = false;
    }, 120);
  }

  cancelDrag(): void {
    this.dragAccepted = false;
    this.dragging = false;
    this.dragOffset = 0;
  }

  beginPress(index: number): void {
    this.clickGlowIndex = index;
    this.clickGlowExpanded = false;
    if (!this.glassStyle().clickGlowEnabled) {
      return;
    }
    setTimeout(() => {
      if (this.clickGlowIndex === index) {
        this.clickGlowExpanded = true;
      }
    }, 16);
  }

  endPress(index: number): void {
    if (!this.glassStyle().clickGlowEnabled) {
      this.clickGlowIndex = -1;
      return;
    }
    setTimeout(() => {
      if (this.clickGlowIndex === index) {
        this.clickGlowIndex = -1;
        this.clickGlowExpanded = false;
      }
    }, this.glassStyle().clickGlowDuration);
  }

  @Builder
  DockSelectionLens() {
    Row()
      .width('20%')
      .height(60)
      .position({ x: `${this.activeTab * 20}%`, y: 0 })
      .translate({ x: this.dragOffset, y: 0 })
      .scale({
        x: this.dragging ? MotionSpec.scale(this.reduceMotion, 1.08) : 1.0,
        y: this.dragging ? MotionSpec.scale(this.reduceMotion, 0.94) : 1.0
      })
      .linearGradient({
        angle: 135,
        colors: [
          [this.glassStyle().highlightColor, 0.0],
          [this.glassStyle().selectedSurfaceColor, 0.56],
          [this.darkMode ? '#3344A8FF' : '#225B68F2', 1.0]
        ]
      })
      .border({ width: this.dragging ? 1.2 : 0.7, color: this.glassStyle().selectedBorderColor })
      .borderRadius(26)
      .shadow({
        radius: this.dragging ? 12 : 8,
        color: this.darkMode ? '#3344A8FF' : '#225B68F2',
        offsetY: 2
      })
      .opacity(0.96)
      .hitTestBehavior(HitTestMode.None)
      .animation({ duration: this.dragging ? 0 : this.glassStyle().motionDuration, curve: Curve.Smooth })
  }

  @Builder
  DockItemView(item: DockItem) {
    Stack({ alignContent: Alignment.Center }) {
      if (this.clickGlowIndex === item.index) {
        Row()
          .width(this.glassStyle().clickGlowDiameter)
          .height(this.glassStyle().clickGlowDiameter)
          .borderRadius(this.glassStyle().clickGlowDiameter / 2)
          .radialGradient({
            center: ['50%', '50%'],
            radius: '50%',
            colors: [
              [this.palette().primary, 0.0],
              [this.glassStyle().clickGlowColor, 0.40],
              [this.darkMode ? '#389CC7D0' : '#385B68F2', 0.72],
              [this.darkMode ? '#009CC7D0' : '#005B68F2', 1.0]
            ]
          })
          .scale({
            x: this.glassStyle().clickGlowEnabled ? (this.clickGlowExpanded ? 1.08 : 0.58) : 1.0,
            y: this.glassStyle().clickGlowEnabled ? (this.clickGlowExpanded ? 1.08 : 0.58) : 1.0
          })
          .opacity(this.glassStyle().clickGlowEnabled ? (this.clickGlowExpanded ? 0.0 : 0.72) : 0.42)
          .hitTestBehavior(HitTestMode.None)
          .animation({ duration: this.glassStyle().clickGlowDuration, curve: Curve.Smooth })
      }
      Column({ space: 3 }) {
        Stack({ alignContent: Alignment.Center }) {
          if (item.index === 3 && this.isVisualTab(item.index)) {
            Image($r('app.media.ph_robot'))
              .width(this.isVisualTab(item.index) ? 24 : 22)
              .height(this.isVisualTab(item.index) ? 24 : 22)
              .objectFit(ImageFit.Contain)
              .scale({
                x: this.isVisualTab(item.index) ? MotionSpec.scale(this.reduceMotion, 1.12) : 1.0,
                y: this.isVisualTab(item.index) ? MotionSpec.scale(this.reduceMotion, 1.12) : 1.0
              })
              .animation({ duration: MotionSpec.duration(this.reduceMotion, MotionDuration.STATE), curve: Curve.Smooth })
          } else {
            SymbolGlyph(item.symbol)
              .fontSize(this.isVisualTab(item.index) ? 23 : 21)
              .fontWeight(this.isVisualTab(item.index) ? FontWeight.Bold : FontWeight.Medium)
              .fontColor([this.isVisualTab(item.index) ? this.palette().primary : this.palette().muted])
              .scale({
                x: this.isVisualTab(item.index) ? MotionSpec.scale(this.reduceMotion, 1.12) : 1.0,
                y: this.isVisualTab(item.index) ? MotionSpec.scale(this.reduceMotion, 1.12) : 1.0
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
          .fontColor(this.isVisualTab(item.index) ? this.palette().primary : this.palette().muted)
          .fontSize(10)
          .fontWeight(this.isVisualTab(item.index) ? FontWeight.Bold : FontWeight.Medium)
          .maxLines(1)
          .opacity(this.isVisualTab(item.index) ? 1.0 : 0.82)
      }
      .width('100%')
      .height('100%')
      .justifyContent(FlexAlign.Center)
      .alignItems(HorizontalAlign.Center)
    }
    .layoutWeight(1)
    .height(60)
    .clip(true)
    .animation({ duration: this.glassStyle().motionDuration, curve: Curve.Smooth })
    .onTouch((event: TouchEvent) => {
      if (event.type === TouchType.Down) {
        this.beginPress(item.index);
      } else if (event.type === TouchType.Up || event.type === TouchType.Cancel) {
        this.endPress(item.index);
      }
    })
    .gesture(
      PanGesture({ fingers: 1, direction: PanDirection.Horizontal, distance: 4 })
        .onActionStart(() => this.beginDrag(item.index))
        .onActionUpdate((event: GestureEvent) => this.updateDrag(event))
        .onActionEnd(() => this.finishDrag())
        .onActionCancel(() => this.cancelDrag())
    )
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

        this.DockSelectionLens()

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
      .onAreaChange((_oldValue: Area, newValue: Area) => {
        if (typeof newValue.width === 'number') {
          this.dockWidth = newValue.width;
        }
      })
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
