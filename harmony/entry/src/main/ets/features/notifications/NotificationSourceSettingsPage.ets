import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { NotificationIngestService } from '../../data/notification/NotificationIngestService';
import { NotificationInbox } from '../../data/notification/NotificationInbox';
import { DEFAULT_SOURCE_SETTINGS, NotificationSource, NotificationSourceResolver, NotificationSourceSettings } from '../../data/notification/NotificationSource';

@Component
export struct NotificationSourceSettingsPage {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop source: NotificationSource = NotificationSource.WECHAT;
  @State sourceSettings: NotificationSourceSettings = {
    wechatEnabled: DEFAULT_SOURCE_SETTINGS.wechatEnabled,
    wecomEnabled: DEFAULT_SOURCE_SETTINGS.wecomEnabled,
    xuexitongEnabled: DEFAULT_SOURCE_SETTINGS.xuexitongEnabled,
    qqEnabled: DEFAULT_SOURCE_SETTINGS.qqEnabled,
    otherEnabled: DEFAULT_SOURCE_SETTINGS.otherEnabled
  };
  @State groups: string[] = [];
  @State newGroupName: string = '';
  ingestService: NotificationIngestService | null = null;
  onBack: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void { this.loadPreferences(); }

  async loadPreferences(): Promise<void> {
    if (this.ingestService === null) return;
    this.sourceSettings = await this.ingestService.loadSourceSettings();
    if (this.source === NotificationSource.WECHAT) this.groups = await this.ingestService.loadWechatWhitelist();
    else if (this.source === NotificationSource.WECOM) this.groups = await this.ingestService.loadWecomWhitelist();
    else if (this.source === NotificationSource.QQ) this.groups = await this.ingestService.loadQqWhitelist();
  }

  sourceEnabled(): boolean {
    if (this.source === NotificationSource.WECHAT) return this.sourceSettings.wechatEnabled;
    if (this.source === NotificationSource.WECOM) return this.sourceSettings.wecomEnabled;
    if (this.source === NotificationSource.QQ) return this.sourceSettings.qqEnabled;
    return false;
  }

  async setSourceEnabled(enabled: boolean): Promise<void> {
    const next: NotificationSourceSettings = NotificationInbox.updateSourceSetting(this.sourceSettings, this.source, enabled);
    this.sourceSettings = next;
    if (this.ingestService !== null) await this.ingestService.saveSourceSettings(next);
  }

  async addGroup(): Promise<void> {
    const group: string = this.newGroupName.trim();
    if (this.ingestService === null || group.length === 0) return;
    if (this.source === NotificationSource.WECHAT) this.groups = await this.ingestService.addWechatWhitelistGroup(group);
    else if (this.source === NotificationSource.WECOM) this.groups = await this.ingestService.addWecomWhitelistGroup(group);
    else if (this.source === NotificationSource.QQ) this.groups = await this.ingestService.addQqWhitelistGroup(group);
    this.newGroupName = '';
  }

  async removeGroup(group: string): Promise<void> {
    if (this.ingestService === null) return;
    if (this.source === NotificationSource.WECHAT) this.groups = await this.ingestService.removeWechatWhitelistGroup(group);
    else if (this.source === NotificationSource.WECOM) this.groups = await this.ingestService.removeWecomWhitelistGroup(group);
    else if (this.source === NotificationSource.QQ) this.groups = await this.ingestService.removeQqWhitelistGroup(group);
  }

  build() {
    Column() {
      SecondaryHeader({
        title: `${NotificationSourceResolver.sourceDisplayName(this.source)}设置`,
        subtitle: '管理导入来源与群聊白名单',
        darkMode: this.darkMode,
        reduceMotion: this.reduceMotion,
        onBack: this.onBack
      })
      Scroll() {
        Column({ space: 14 }) {
          Column({ space: 8 }) {
            Row() {
              Column({ space: 4 }) {
                Text(`${NotificationSourceResolver.sourceDisplayName(this.source)}通知`)
                  .fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
                Text('控制已导入通知是否进入整理流程').fontColor(this.palette().muted).fontSize(11)
              }.layoutWeight(1).alignItems(HorizontalAlign.Start)
              Toggle({ type: ToggleType.Switch, isOn: this.sourceEnabled() })
                .selectedColor(this.palette().primary)
                .onChange((checked: boolean) => this.setSourceEnabled(checked))
            }.width('100%').alignItems(VerticalAlign.Center)
            Text('鸿蒙普通应用无法直接读取微信、企业微信或 QQ 的系统通知；此开关不会授予系统监听权限。')
              .fontColor(this.palette().muted).fontSize(10).lineHeight(17).width('100%')
          }.width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)

          Column({ space: 12 }) {
            Text('群聊白名单').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).width('100%')
            Text('仅精确匹配以下群聊名称。名单为空时，此来源的群聊通知不会进入自动整理。')
              .fontColor(this.palette().muted).fontSize(11).lineHeight(18).width('100%')
            Row({ space: 8 }) {
              TextInput({ text: this.newGroupName, placeholder: '输入完整群聊名称' })
                .layoutWeight(1).height(44).fontSize(13).fontColor(this.palette().text)
                .backgroundColor(this.palette().background).borderRadius(11)
                .onChange((value: string) => this.newGroupName = value)
              Button('添加').height(44).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(11)
                .enabled(this.newGroupName.trim().length > 0).onClick(() => this.addGroup())
            }.width('100%')

            if (this.groups.length === 0) {
              Row({ space: 7 }) {
                SymbolGlyph($r('sys.symbol.message')).fontSize(16).fontColor([this.palette().muted])
                Text('尚未添加群聊').fontColor(this.palette().muted).fontSize(12)
              }.width('100%').height(64).justifyContent(FlexAlign.Center)
            } else {
              ForEach(this.groups, (group: string, index: number) => {
                Row({ space: 10 }) {
                  SymbolGlyph($r('sys.symbol.message')).fontSize(16).fontColor([this.palette().primary])
                  Text(group).fontColor(this.palette().text).fontSize(13).layoutWeight(1).maxLines(1)
                  Button('移除').fontColor(this.palette().danger).fontSize(11).height(40)
                    .backgroundColor('#00000000').padding({ left: 8, right: 8 }).onClick(() => this.removeGroup(group))
                }.width('100%').padding({ top: 5, bottom: 5 }).alignItems(VerticalAlign.Center)
                if (index < this.groups.length - 1) { Divider().color(this.palette().line) }
              }, (group: string) => group)
            }
          }.width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)
        }.width('100%').padding({ left: 14, right: 14, bottom: 28 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
