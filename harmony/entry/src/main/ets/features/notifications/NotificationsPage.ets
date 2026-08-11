import { NoticeItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct NotificationsPage {
  @Prop notices: NoticeItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @State unreadOnly: boolean = false;
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  visible(): NoticeItem[] { return this.unreadOnly ? this.notices.filter((item: NoticeItem) => item.unread === true) : this.notices; }

  @Builder SourceRow(symbol: Resource, title: string, subtitle: string, status: string) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph(symbol).fontSize(20).fontColor([this.palette().primary]) }
        .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text(title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
        Text(subtitle).fontColor(this.palette().muted).fontSize(10).maxLines(1)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Text(status).fontColor(this.palette().success).fontSize(10).fontWeight(FontWeight.Medium)
    }.width('100%').padding({ top: 10, bottom: 10 })
  }

  @Builder NoticeRow(item: NoticeItem) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.bell')).fontSize(20).fontColor([this.palette().primary])
        if (item.unread === true) { Circle().width(7).height(7).fill('#FFE35F42').position({ x: 30, y: 4 }) }
      }.width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 4 }) {
        Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(item.content ?? '暂无详细内容').fontColor(this.palette().muted).fontSize(10).maxLines(2)
        Text(`${item.source ?? '校园通知'} · ${(item.time ?? '').substring(0, Math.min(10, (item.time ?? '').length))}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding({ top: 12, bottom: 12 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))
    .gesture(
      TapGesture({ count: 1 })
        .onAction(() => {
          animateTo({ duration: 150, curve: Curve.EaseInOut }, () => {
          })
        })
    )
  }

  build() {
    Column() {
      SecondaryHeader({ title: '通知整理', subtitle: '集中接收并整理校园通知', darkMode: this.darkMode, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          Text('通知来源').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold).width('100%')
          Column() {
            this.SourceRow($r('sys.symbol.cloud'), '校园服务器', '公告、课程与截止事项', '已连接')
            Divider().color(this.palette().line)
            this.SourceRow($r('sys.symbol.book'), '学习通', '作为补充来源', '可设置')
            Divider().color(this.palette().line)
            this.SourceRow($r('sys.symbol.shield_checkered'), '系统通知', '鸿蒙端使用站内通知替代第三方监听', '安全模式')
          }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
          Row() {
            Text('最近收集').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
            Blank()
            Text(this.unreadOnly ? '只看未读' : '全部').fontColor(this.palette().primary).fontSize(11).onClick(() => this.unreadOnly = !this.unreadOnly)
            Text('刷新').fontColor(this.palette().muted).fontSize(11).margin({ left: 14 }).onClick(() => this.onRefresh())
          }.width('100%')
          Column() {
            if (this.loading) { LoadingProgress().width(34).height(34).color(this.palette().primary).margin(28) }
            else if (this.visible().length === 0) { Text('暂无校园通知').fontColor(this.palette().muted).fontSize(12).padding(30) }
            else {
              ForEach(this.visible(), (item: NoticeItem, index: number) => { this.NoticeRow(item); if (index < this.visible().length - 1) { Divider().color(this.palette().line) } }, (item: NoticeItem) => item.id)
            }
          }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
