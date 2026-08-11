import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

@Component
export struct ProfilePage {
  @Prop darkMode: boolean = false;
  @Prop name: string = '林知夏';
  @Prop detail: string = '计算机科学与技术 · 大三';
  onNavigate: (route: string) => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  @Builder QuickAction(label: string, symbol: Resource, route: string, accent: boolean) {
    Column({ space: 9 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph(symbol).fontSize(23).fontColor([accent ? this.palette().accent : this.palette().primary])
      }.width(43).height(43).backgroundColor(accent ? '#1FE08A4E' : this.palette().soft).borderRadius(14)
      Text(label).fontColor(this.palette().text).fontSize(12).fontWeight(FontWeight.Medium)
    }.layoutWeight(1).height('100%').justifyContent(FlexAlign.Center).onClick(() => this.onNavigate(route))
  }

  @Builder MenuRow(label: string, symbol: Resource, route: string) {
    Row() {
      SymbolGlyph(symbol).fontSize(27).fontColor([this.palette().primary])
      Text(label).fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Medium).layoutWeight(1).margin({ left: 18 })
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(21).fontColor([this.palette().muted])
    }.width('100%').height(70).alignItems(VerticalAlign.Center).onClick(() => this.onNavigate(route))
    .gesture(
      TapGesture({ count: 1 })
        .onAction(() => {
          animateTo({ duration: 200, curve: Curve.FastOutSlowIn }, () => {
          })
        })
    )
  }

  build() {
    Scroll() {
      Column({ space: 14 }) {
        Stack({ alignContent: Alignment.TopStart }) {
          Column() {}
            .width('100%').height(318)
            .linearGradient({ angle: 90, colors: this.darkMode ? [['#FF17384A',0],['#FF2F6486',1]] : [['#FF4E5EDB',0],['#FF6E79F5',1]] })
            .borderRadius({ bottomLeft: 30, bottomRight: 30 })
          Column() {
            Row() {
              Column({ space: 2 }) {
                Text('我的').fontColor('#FFFFFFFF').fontSize(28).fontWeight(FontWeight.Bold)
                Text('今天也照顾好自己的节奏').fontColor('#BDFFFFFF').fontSize(11)
              }.alignItems(HorizontalAlign.Start)
              Blank()
              Stack({ alignContent: Alignment.Center }) {
                SymbolGlyph($r('sys.symbol.qrcode')).fontSize(22).fontColor(['#FFFFFFFF'])
              }.width(40).height(40).backgroundColor('#1FFFFFFF').borderRadius(20).onClick(() => this.onNavigate('settings'))
            }.width('100%')
            Row() {
              Image($r('app.media.profile_avatar_reference')).width(82).height(82).objectFit(ImageFit.Cover).borderRadius(41)
                .border({ width: 3, color: '#FFFFFFFF' })
              Column({ space: 7 }) {
                Text(this.name).fontColor('#FFFFFFFF').fontSize(24).fontWeight(FontWeight.Bold).maxLines(1)
                Text(this.detail).fontColor('#D6FFFFFF').fontSize(14).maxLines(1)
                Row({ space: 4 }) {
                  SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(11).fontColor(['#E0FFFFFF'])
                  Text('资料已同步到当前账号').fontColor('#E0FFFFFF').fontSize(9)
                }.padding({ left: 9, right: 9, top: 5, bottom: 5 }).backgroundColor('#1FFFFFFF').borderRadius(13)
              }.layoutWeight(1).alignItems(HorizontalAlign.Start).margin({ left: 17 })
              SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(22).fontColor(['#CCFFFFFF'])
            }.width('100%').alignItems(VerticalAlign.Center).margin({ top: 30 }).onClick(() => this.onNavigate('account'))
          }.width('100%').padding({ left: 24, top: 15, right: 20 })
          Row() {
            this.QuickAction('文件', $r('sys.symbol.doc_text'), 'files', false)
            this.QuickAction('活动', $r('sys.symbol.calendar_badge_checkmark'), 'activities', true)
            this.QuickAction('收藏', $r('sys.symbol.bookmark'), 'favorites', false)
            this.QuickAction('设置', $r('sys.symbol.gearshape'), 'settings', false)
          }.width('100%').height(126).padding({ left: 7, right: 7, top: 16, bottom: 16 })
            .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(24)
            .position({ x: 16, y: 256 }).constraintSize({ maxWidth: '91%' })
        }.width('100%').height(382)
        Text('更多服务').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold).width('100%').padding({ left: 20 })
        Column() {
          this.MenuRow('学习与专注', $r('sys.symbol.timer'), 'focus'); Divider().color(this.palette().line).margin({ left: 53 })
          this.MenuRow('通知与提醒', $r('sys.symbol.bell'), 'notifications'); Divider().color(this.palette().line).margin({ left: 53 })
          this.MenuRow('账号与隐私', $r('sys.symbol.person_shield'), 'account'); Divider().color(this.palette().line).margin({ left: 53 })
          this.MenuRow('帮助与反馈', $r('sys.symbol.message'), 'counselor'); Divider().color(this.palette().line).margin({ left: 53 })
          this.MenuRow('关于 CampusMate', $r('sys.symbol.info_circle'), 'about')
        }.width('100%').padding({ left: 16, right: 16, top: 3, bottom: 3 })
          .backgroundColor(this.palette().surface).border({ width: 1, color: this.palette().line }).borderRadius(22)
        Blank().height(102)
      }.width('100%')
    }.width('100%').height('100%').scrollBar(BarState.Off).backgroundColor(this.palette().background)
  }
}
