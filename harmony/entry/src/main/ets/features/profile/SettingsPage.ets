import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct SettingsPage {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop backendOnline: boolean = true;
  onBack: () => void = () => {};
  onThemeChange: (value: boolean) => void = () => {};
  onMotionChange: (value: boolean) => void = () => {};
  onNavigate: (target: string) => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  @Builder ToggleRow(symbol: Resource, title: string, subtitle: string, value: boolean, onChange: (value: boolean) => void) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph(symbol).fontSize(20).fontColor([this.palette().primary]) }
        .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text(title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
        Text(subtitle).fontColor(this.palette().muted).fontSize(10).maxLines(2)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Toggle({ type: ToggleType.Switch, isOn: value }).onChange(onChange)
    }.width('100%').padding({ top: 11, bottom: 11 })
  }

  @Builder LinkRow(symbol: Resource, title: string, subtitle: string, target: string) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph(symbol).fontSize(20).fontColor([this.palette().primary]) }
        .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text(title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
        Text(subtitle).fontColor(this.palette().muted).fontSize(10)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(17).fontColor([this.palette().muted])
    }.width('100%').padding({ top: 11, bottom: 11 }).onClick(() => this.onNavigate(target))

  }

  build() {
    Column() {
      SecondaryHeader({ title: '系统设置', subtitle: '个性化你的校园助手', darkMode: this.darkMode, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          Text('显示与动效').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).width('100%')
          Column() {
            this.ToggleRow($r('sys.symbol.moon'), '深色模式', this.darkMode ? '已使用夜间配色，减少暗处眩光' : '切换为更适合夜间的深色界面', this.darkMode, (value: boolean) => this.onThemeChange(value))
            Divider().color(this.palette().line)
            this.ToggleRow($r('sys.symbol.slider_horizontal_2'), '减少动态效果', '减少页面进入与状态切换动画', this.reduceMotion, (value: boolean) => this.onMotionChange(value))
          }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
          Text('提醒与陪伴').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).width('100%')
          Column() {
            this.LinkRow($r('sys.symbol.bell'), '截止提醒', '待办临近截止时发送系统通知', 'notifications')
            Divider().color(this.palette().line)
            this.LinkRow($r('sys.symbol.robot'), 'AI 与模型共建', '查看校园助手能力与隐私说明', 'about')
          }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
          Text('数据与服务').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).width('100%')
          Row({ space: 11 }) {
            Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.cloud')).fontSize(20).fontColor([this.palette().primary]) }
              .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
            Column({ space: 3 }) {
              Text('后端服务').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
              Text(this.backendOnline ? '已连接（real_backend）' : '暂未连接').fontColor(this.palette().muted).fontSize(10)
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Circle().width(9).height(9).fill(this.backendOnline ? this.palette().success : '#FFE35F42')
          }.width('100%').padding(13).backgroundColor(this.palette().surface).borderRadius(18)
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
