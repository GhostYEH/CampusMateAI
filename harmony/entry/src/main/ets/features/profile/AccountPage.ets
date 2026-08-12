import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct AccountPage {
  @Prop darkMode: boolean = false;
  @Prop name: string = '';
  @Prop detail: string = '';
  onBack: () => void = () => {};
  onSignOut: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  @Builder InfoRow(label: string, value: string) {
    Row() {
      Text(label).fontColor(this.palette().muted).fontSize(12)
      Blank()
      Text(value).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Medium).maxLines(1)
    }.width('100%').padding({ top: 14, bottom: 14 })
  }

  build() {
    Column() {
      SecondaryHeader({ title: '账号与隐私', subtitle: '个人资料和账号信息', darkMode: this.darkMode, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 14 }) {
          Column({ space: 10 }) {
            Image($r('app.media.profile_avatar_reference')).width(86).height(86).objectFit(ImageFit.Cover).borderRadius(43)
            Text(this.name).fontColor(this.palette().text).fontSize(21).fontWeight(FontWeight.Bold)
            Text(this.detail).fontColor(this.palette().muted).fontSize(12)
          }.width('100%').padding({ top: 22, bottom: 20 }).backgroundColor(this.palette().surface).borderRadius(20)
          Column() {
            this.InfoRow('登录账号', this.name)
            Divider().color(this.palette().line)
            this.InfoRow('身份信息', this.detail)
            Divider().color(this.palette().line)
            this.InfoRow('数据同步', '已连接当前账号')
          }.width('100%').padding({ left: 15, right: 15 }).backgroundColor(this.palette().surface).borderRadius(18)
          Row({ space: 9 }) {
            SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(18).fontColor([this.palette().success])
            Text('密码和令牌不会在界面中明文显示').fontColor(this.palette().muted).fontSize(10)
          }.width('100%').padding(13).backgroundColor(this.palette().surface).borderRadius(15)
          Button('退出当前账号').width('100%').height(50).backgroundColor('#FFFFECEA').fontColor('#FFC25450').onClick(() => this.onSignOut())

        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
