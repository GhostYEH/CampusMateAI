import { LocalCapturedNotice, ExtractResult, TaskItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { NotificationIngestService } from '../../data/notification/NotificationIngestService';
import { NotificationCaptureCapability } from '../../data/notification/NotificationCaptureCapability';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';
import { NotificationInbox } from '../../data/notification/NotificationInbox';
import { DEFAULT_SOURCE_SETTINGS, NotificationSource, NotificationSourceResolver, NotificationSourceSettings } from '../../data/notification/NotificationSource';
import { promptAction } from '@kit.ArkUI';
import { ChaoxingAccountStatus, ChaoxingStatusMapper } from '../../data/chaoxing/ChaoxingAccount';

@Component
export struct NotificationsPage {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @Prop localNotices: LocalCapturedNotice[] = [];
  @Prop chaoxingStatus: ChaoxingAccountStatus = ChaoxingStatusMapper.unavailable();
  @Prop view: string = 'main';
  @Prop selectedLocalId: string = '';
  @Prop settingsSource: NotificationSource | null = null;
  @Prop @Watch('onManualSeedChange') manualSeed: string = '';
  @State filterSource: NotificationSource | null = null;
  @State sourceSettings: NotificationSourceSettings = {
    wechatEnabled: DEFAULT_SOURCE_SETTINGS.wechatEnabled,
    wecomEnabled: DEFAULT_SOURCE_SETTINGS.wecomEnabled,
    xuexitongEnabled: DEFAULT_SOURCE_SETTINGS.xuexitongEnabled,
    qqEnabled: DEFAULT_SOURCE_SETTINGS.qqEnabled,
    otherEnabled: DEFAULT_SOURCE_SETTINGS.otherEnabled,
  };
  @State wechatGroups: string[] = [];
  @State wecomGroups: string[] = [];
  @State qqGroups: string[] = [];
  @State newGroupName: string = '';
  @State manualText: string = '';
  @State extracting: boolean = false;
  @State hasExtractResult: boolean = false;
  @State resultError: string = '';
  @State resultTitle: string = '';
  @State resultSource: string = '';
  @State resultDeadline: string = '';
  @State resultConfidence: number = 0;
  @State resultTasks: string[] = [];
  @State editTitle: string = '';
  @State editDeadline: string = '';
  @State editSource: string = '';
  @State saving: boolean = false;
  @State saved: boolean = false;
  ingestService: NotificationIngestService | null = null;
  onBack: () => void = () => {};
  onTaskSaved: () => void = () => {};
  onLocalNoticesChanged: () => void = () => {};
  onOpenDetail: (id: string) => void = (_: string) => {};
  onOpenSourceSettings: (source: NotificationSource) => void = (_: NotificationSource) => {};
  onOpenChaoxing: () => void = () => {};
  onPrepareManualExtract: (content: string) => void = (_: string) => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  captureCapability(): NotificationCaptureCapability { return NotificationCaptureCapability.ordinaryPhoneBuild(); }
  visibleLocalNotices(): LocalCapturedNotice[] { return NotificationInbox.filter(this.localNotices, this.filterSource); }
  selectedLocalNotice(): LocalCapturedNotice | undefined {
    return this.localNotices.find((item: LocalCapturedNotice) => item.id === this.selectedLocalId);
  }
  twoDigits(value: number): string { return value < 10 ? `0${value}` : `${value}`; }
  formatLocalTime(value: string): string {
    const date: Date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return `${date.getFullYear()}-${this.twoDigits(date.getMonth() + 1)}-${this.twoDigits(date.getDate())} ${this.twoDigits(date.getHours())}:${this.twoDigits(date.getMinutes())}`;
  }

  aboutToAppear(): void {
    if (this.manualSeed.length > 0) this.manualText = this.manualSeed;
    this.loadNotificationPreferences();
  }

  onManualSeedChange(): void {
    if (this.manualSeed.length > 0) {
      this.manualText = this.manualSeed;
      this.hasExtractResult = false;
      this.saved = false;
    }
  }

  async loadNotificationPreferences(): Promise<void> {
    if (this.ingestService === null) return;
    this.sourceSettings = await this.ingestService.loadSourceSettings();
    this.wechatGroups = await this.ingestService.loadWechatWhitelist();
    this.wecomGroups = await this.ingestService.loadWecomWhitelist();
    this.qqGroups = await this.ingestService.loadQqWhitelist();
  }

  sourceEnabled(source: NotificationSource): boolean {
    if (source === NotificationSource.WECHAT) return this.sourceSettings.wechatEnabled;
    if (source === NotificationSource.WECOM) return this.sourceSettings.wecomEnabled;
    if (source === NotificationSource.XUEXITONG) return this.sourceSettings.xuexitongEnabled;
    if (source === NotificationSource.QQ) return this.sourceSettings.qqEnabled;
    return false;
  }

  async setSourceEnabled(source: NotificationSource, enabled: boolean): Promise<void> {
    const next: NotificationSourceSettings = NotificationInbox.updateSourceSetting(this.sourceSettings, source, enabled);
    this.sourceSettings = next;
    if (this.ingestService !== null) await this.ingestService.saveSourceSettings(next);
  }

  currentWhitelist(): string[] {
    if (this.settingsSource === NotificationSource.WECHAT) return this.wechatGroups;
    if (this.settingsSource === NotificationSource.WECOM) return this.wecomGroups;
    if (this.settingsSource === NotificationSource.QQ) return this.qqGroups;
    return [];
  }

  async addWhitelistGroup(): Promise<void> {
    if (this.ingestService === null || this.settingsSource === null) return;
    if (this.settingsSource === NotificationSource.WECHAT) this.wechatGroups = await this.ingestService.addWechatWhitelistGroup(this.newGroupName);
    if (this.settingsSource === NotificationSource.WECOM) this.wecomGroups = await this.ingestService.addWecomWhitelistGroup(this.newGroupName);
    if (this.settingsSource === NotificationSource.QQ) this.qqGroups = await this.ingestService.addQqWhitelistGroup(this.newGroupName);
    this.newGroupName = '';
  }

  async removeWhitelistGroup(group: string): Promise<void> {
    if (this.ingestService === null || this.settingsSource === null) return;
    if (this.settingsSource === NotificationSource.WECHAT) this.wechatGroups = await this.ingestService.removeWechatWhitelistGroup(group);
    if (this.settingsSource === NotificationSource.WECOM) this.wecomGroups = await this.ingestService.removeWecomWhitelistGroup(group);
    if (this.settingsSource === NotificationSource.QQ) this.qqGroups = await this.ingestService.removeQqWhitelistGroup(group);
  }

  async deleteLocalNotice(id: string): Promise<void> {
    if (this.ingestService === null) return;
    await this.ingestService.deleteLocalNotice(id);
    if (this.selectedLocalId === id) this.onBack();
    this.onLocalNoticesChanged();
  }

  confirmClearLocalNotices(): void {
    promptAction.showDialog({
      title: '清空最近收集', message: '将删除全部本地自动收集记录，此操作无法撤销。',
      buttons: [{ text: '取消', color: this.palette().muted }, { text: '清空', color: this.palette().danger }],
    }).then((res: promptAction.ShowDialogSuccessResponse) => {
      if (res.index === 1) this.clearLocalNotices();
    }).catch(() => {});
  }

  async clearLocalNotices(): Promise<void> {
    if (this.ingestService === null) return;
    await this.ingestService.clearLocalNotices();
    this.onLocalNoticesChanged();
  }

  async doExtract(text: string): Promise<void> {
    if (this.ingestService === null) {
      this.extracting = false;
      this.resultError = '通知服务未初始化';
      this.hasExtractResult = true;
      return;
    }
    try {
      const result: ExtractResult = await this.ingestService.extractNotice(text);
      this.resultError = result.error ?? '';
      this.resultTitle = result.title ?? '';
      this.resultSource = result.source ?? '';
      this.resultDeadline = result.deadline ?? '待设置';
      this.resultConfidence = result.confidence ?? 0;
      this.resultTasks = result.tasks ?? [];
      this.editTitle = result.title ?? '';
      this.editSource = result.source ?? '';
      this.editDeadline = result.deadline ?? '待设置';
      this.saved = false;
      this.hasExtractResult = true;
    } catch (e) {
      this.resultError = (e as Error).message;
      this.hasExtractResult = true;
    } finally {
      this.extracting = false;
    }
  }

  async doSaveTask(title: string, deadline: string, source: string): Promise<void> {
    if (this.ingestService === null) {
      this.saving = false;
      return;
    }
    try {
      const task: TaskItem | null = await this.ingestService.createTask(title, deadline, source, '');
      if (task !== null) {
        this.saved = true;
        this.onTaskSaved();
      }
    } catch { } finally { this.saving = false; }
  }

  @Builder SourceRow(symbol: Resource, source: NotificationSource, title: string, subtitle: string, whitelistCount: number) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph(symbol).fontSize(20).fontColor([this.palette().primary]) }
        .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text(title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
        Text(whitelistCount >= 0 ? `${subtitle} · ${whitelistCount} 个群聊` : subtitle).fontColor(this.palette().muted).fontSize(10).maxLines(1)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Button('设置').fontColor(this.palette().primary).fontSize(11).height(40).backgroundColor('#00000000').padding({ left: 8, right: 8 }).onClick(() => {
        this.onOpenSourceSettings(source);
        this.newGroupName = '';
      })
      Toggle({ type: ToggleType.Switch, isOn: this.sourceEnabled(source) })
        .selectedColor(this.palette().primary)
        .onChange((checked: boolean) => this.setSourceEnabled(source, checked))
    }.width('100%').padding({ top: 10, bottom: 10 })
  }

  @Builder ChaoxingSourceRow() {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.book')).fontSize(20).fontColor([this.palette().primary]) }
        .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text('学习通').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
        Text(this.chaoxingStatus.connected ? this.chaoxingStatus.summary : '同步课程、作业与课程通知')
          .fontColor(this.palette().muted).fontSize(10).maxLines(1)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Text(this.chaoxingStatus.label)
        .fontColor(this.chaoxingStatus.connected ? this.palette().success : this.palette().muted)
        .fontSize(10).fontWeight(FontWeight.Medium)
      SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(14).fontColor([this.palette().muted])
    }.width('100%').padding({ top: 10, bottom: 10 }).onClick(() => this.onOpenChaoxing())
  }

  @Builder LocalNoticeRow(item: LocalCapturedNotice) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) {
        SymbolGlyph($r('sys.symbol.info_circle')).fontSize(18).fontColor([this.palette().accent])
      }.width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 4 }) {
        Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(item.content).fontColor(this.palette().muted).fontSize(10).maxLines(2)
        Text(`${item.source} · ${item.source_type} · ${this.formatLocalTime(item.time)}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start).onClick(() => this.onOpenDetail(item.id))
      Button('删除').fontColor(this.palette().danger).fontSize(10).height(40).backgroundColor('#00000000').padding({ left: 8, right: 8 })
        .onClick(() => this.deleteLocalNotice(item.id))
    }.width('100%').padding({ top: 12, bottom: 12 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 12) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
  }

  @Builder LocalNoticeDetail(item: LocalCapturedNotice) {
    Scroll() {
      Column({ space: 13 }) {
        Column({ space: 8 }) {
          Text(item.title).fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold).width('100%')
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.clock')).fontSize(13).fontColor([this.palette().muted])
            Text(this.formatLocalTime(item.time)).fontColor(this.palette().muted).fontSize(11)
            Text('·').fontColor(this.palette().muted)
            Text(item.source_type).fontColor(this.palette().muted).fontSize(11)
          }
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
        Column({ space: 6 }) {
          Text('通知正文').fontColor(this.palette().text).fontSize(14).fontWeight(FontWeight.Bold)
          Text(item.content).fontColor(this.palette().muted).fontSize(13).lineHeight(22)
        }.width('100%').padding(14).backgroundColor(this.palette().surface).borderRadius(16)
        Button('手动整理此通知').width('100%').height(44).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(12)
          .onClick(() => {
            this.onPrepareManualExtract(item.content);
            this.onBack();
          })
        Button('删除记录').width('100%').height(42).backgroundColor(this.palette().surface).fontColor(this.palette().danger).borderRadius(12)
          .onClick(() => this.deleteLocalNotice(item.id))
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
  }

  @Builder FilterChip(label: string, source: NotificationSource | null) {
    Text(label).fontSize(11).fontWeight(FontWeight.Medium)
      .fontColor(this.filterSource === source ? '#FFFFFFFF' : this.palette().muted)
      .backgroundColor(this.filterSource === source ? this.palette().primary : this.palette().surface)
      .borderRadius(12).padding({ left: 11, right: 11, top: 7, bottom: 7 })
      .onClick(() => this.filterSource = source)
  }

  @Builder SourceSettingsPage(source: NotificationSource) {
    Scroll() {
      Column({ space: 14 }) {
        Column({ space: 8 }) {
          Row() {
            Column({ space: 3 }) {
              Text(`${NotificationSourceResolver.sourceDisplayName(source)}通知`).fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
              Text('关闭后将不再接收此来源的新记录').fontColor(this.palette().muted).fontSize(10)
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Toggle({ type: ToggleType.Switch, isOn: this.sourceEnabled(source) }).selectedColor(this.palette().primary)
              .onChange((checked: boolean) => this.setSourceEnabled(source, checked))
          }.width('100%')
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)

        if (source === NotificationSource.WECHAT || source === NotificationSource.WECOM || source === NotificationSource.QQ) {
          Column({ space: 11 }) {
            Text('群聊白名单').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold).width('100%')
            Text('仅精确匹配以下群聊名称。名单为空时，此来源的群聊通知不会自动收集。').fontColor(this.palette().muted).fontSize(11).lineHeight(18).width('100%')
            Row({ space: 8 }) {
              TextInput({ text: this.newGroupName, placeholder: '输入完整群聊名称' })
                .layoutWeight(1).height(40).fontSize(12).fontColor(this.palette().text)
                .backgroundColor(this.palette().background).borderRadius(10)
                .onChange((value: string) => this.newGroupName = value)
              Button('添加').height(40).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').borderRadius(10)
                .enabled(this.newGroupName.trim().length > 0).onClick(() => this.addWhitelistGroup())
            }.width('100%')
            if (this.currentWhitelist().length === 0) {
              Text('尚未添加群聊').fontColor(this.palette().muted).fontSize(11).padding({ top: 12, bottom: 12 })
            } else {
              ForEach(this.currentWhitelist(), (group: string, index: number) => {
                Row() {
                  Text(group).fontColor(this.palette().text).fontSize(12).layoutWeight(1)
                  Button('删除').fontColor(this.palette().danger).fontSize(11).height(40).backgroundColor('#00000000').padding({ left: 10, right: 10 })
                    .onClick(() => this.removeWhitelistGroup(group))
                }.width('100%').padding({ top: 5, bottom: 5 })
                if (index < this.currentWhitelist().length - 1) { Divider().color(this.palette().line) }
              }, (group: string) => group)
            }
          }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
        } else {
          Column({ space: 7 }) {
            Text('学习通来源').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold).width('100%')
            Text('学习通通过应用内已连接的账号与后端同步，不需要配置群聊白名单。').fontColor(this.palette().muted).fontSize(11).lineHeight(18).width('100%')
          }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
        }
      }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
    }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
  }

  @Builder ManualExtractCard() {
    Column({ space: 10 }) {
      Row({ space: 8 }) {
        SymbolGlyph($r('sys.symbol.bolt')).fontSize(18).fontColor([this.palette().primary])
        Text('手动整理').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
        Blank()
        Text('粘贴通知文本自动提取').fontColor(this.palette().muted).fontSize(10)
      }.width('100%')
      TextArea({ text: this.manualText, placeholder: '粘贴微信、QQ或学习通通知内容，自动提取事务并新建日程...' })
        .width('100%').height(90).fontSize(13).fontColor(this.palette().text)
        .backgroundColor(this.palette().background).borderRadius(12)
        .border({ width: 1, color: this.palette().line })
        .onChange((value: string) => { this.manualText = value; this.hasExtractResult = false; this.saved = false; })
      Button(this.extracting ? '提取中...' : '开始整理')
        .width('100%').height(44).backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
        .borderRadius(12).enabled(this.manualText.trim().length > 0 && !this.extracting)
        .onClick(() => {
          if (this.manualText.trim().length === 0 || this.extracting) { return; }
          this.extracting = true;
          this.hasExtractResult = false;
          this.saved = false;
          this.doExtract(this.manualText.trim());
        })
    }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
  }

  @Builder ExtractResultCard() {
    if (this.hasExtractResult) {
      if (this.resultError.length > 0) {
        Column({ space: 8 }) {
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.exclamationmark_circle')).fontSize(18).fontColor([this.palette().danger])
            Text('提取失败').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
          }
          Text(this.resultError).fontColor(this.palette().muted).fontSize(12).lineHeight(20)
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
      } else {
        Column({ space: 12 }) {
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(18).fontColor([this.palette().success])
            Text('提取结果').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
            Blank()
            Text(`置信度 ${Math.round(this.resultConfidence * 100)}%`).fontColor(this.palette().muted).fontSize(10)
          }.width('100%')
          Column({ space: 6 }) {
            Text('标题').fontColor(this.palette().muted).fontSize(10)
            TextInput({ text: this.editTitle, placeholder: '事务标题' })
              .width('100%').height(42).fontSize(13).fontColor(this.palette().text)
              .backgroundColor(this.palette().background).borderRadius(10)
              .onChange((value: string) => { this.editTitle = value; })
          }.width('100%')
          Row({ space: 10 }) {
            Column({ space: 6 }) {
              Text('来源').fontColor(this.palette().muted).fontSize(10)
              TextInput({ text: this.editSource, placeholder: '来源' })
                .height(42).fontSize(13).fontColor(this.palette().text)
                .backgroundColor(this.palette().background).borderRadius(10)
                .onChange((value: string) => { this.editSource = value; })
            }.layoutWeight(1)
            Column({ space: 6 }) {
              Text('截止时间').fontColor(this.palette().muted).fontSize(10)
              TextInput({ text: this.editDeadline, placeholder: '待设置' })
                .height(42).fontSize(13).fontColor(this.palette().text)
                .backgroundColor(this.palette().background).borderRadius(10)
                .onChange((value: string) => { this.editDeadline = value; })
            }.layoutWeight(1)
          }.width('100%')
          if (this.resultTasks.length > 0) {
            Column({ space: 5 }) {
              Text('提取的待办项').fontColor(this.palette().muted).fontSize(10)
              ForEach(this.resultTasks, (task: string) => {
                Row({ space: 6 }) {
                  SymbolGlyph($r('sys.symbol.circle_fill')).fontSize(6).fontColor([this.palette().primary])
                  Text(task).fontColor(this.palette().text).fontSize(12).layoutWeight(1)
                }.width('100%')
              }, (task: string, index: number) => `${index}-${task}`)
            }.width('100%')
          }
          Button(this.saved ? '已保存到待办' : (this.saving ? '保存中...' : '确认并保存'))
            .width('100%').height(44)
            .backgroundColor(this.saved ? this.palette().success : this.palette().primary)
            .fontColor('#FFFFFFFF').borderRadius(12)
            .enabled(!this.saved && !this.saving && this.editTitle.trim().length > 0)
            .onClick(() => {
              if (this.saved || this.saving || this.editTitle.trim().length === 0) { return; }
              this.saving = true;
              this.doSaveTask(this.editTitle.trim(), this.editDeadline.trim(), this.editSource.trim());
            })
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(18)
      }
    }
  }

  build() {
    Column() {
      SecondaryHeader({
        title: this.view === 'detail' ? '通知详情' : (this.view === 'settings' && this.settingsSource !== null ? `${NotificationSourceResolver.sourceDisplayName(this.settingsSource)}设置` : '通知整理'),
        subtitle: this.view === 'detail' ? '查看本地收集记录' : (this.view === 'settings' && this.settingsSource !== null ? '管理来源与群聊白名单' : '本地收集并整理重要通知'),
        darkMode: this.darkMode,
        reduceMotion: this.reduceMotion,
        onBack: () => this.onBack()
      })
      if (this.view === 'detail' && this.selectedLocalNotice() !== undefined) {
        this.LocalNoticeDetail(this.selectedLocalNotice()!)
      } else if (this.view === 'settings' && this.settingsSource !== null) {
        this.SourceSettingsPage(this.settingsSource)
      } else {
        Scroll() {
          Column({ space: 13 }) {
            Text('通知来源').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold).width('100%')
            Column() {
              this.SourceRow($r('sys.symbol.message'), NotificationSource.WECHAT, '微信', '群聊通知', this.wechatGroups.length)
              Divider().color(this.palette().line)
              this.SourceRow($r('sys.symbol.person_2'), NotificationSource.WECOM, '企业微信', '工作群通知', this.wecomGroups.length)
              Divider().color(this.palette().line)
              this.SourceRow($r('sys.symbol.message'), NotificationSource.QQ, 'QQ', '群聊通知', this.qqGroups.length)
              Divider().color(this.palette().line)
              this.ChaoxingSourceRow()
            }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)

            Column({ space: 8 }) {
              Row({ space: 11 }) {
                Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.shield_checkered')).fontSize(20).fontColor([this.palette().muted]) }
                  .width(42).height(42).backgroundColor(this.palette().soft).borderRadius(13)
                Column({ space: 3 }) {
                  Text('系统通知监听').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
                  Text(this.captureCapability().detail).fontColor(this.palette().muted).fontSize(10).lineHeight(15).maxLines(3)
                }.layoutWeight(1).alignItems(HorizontalAlign.Start)
                Text('不可用').fontColor(this.palette().muted).fontSize(9).fontWeight(FontWeight.Medium)
              }.width('100%')
              Text('当前应用没有系统级通知订阅资质，无法直接读取微信、企业微信或 QQ 的系统通知。可使用学习通同步、后端通知或手动粘贴。')
                .fontColor(this.palette().muted).fontSize(10).lineHeight(16).width('100%')
            }.width('100%').padding(13).backgroundColor(this.palette().surface).borderRadius(18)

            this.ManualExtractCard()
            this.ExtractResultCard()

            Row() {
              Text('最近收集').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
              Blank()
              if (this.localNotices.length > 0) {
                Text('清空').fontColor(this.palette().danger).fontSize(11).onClick(() => this.confirmClearLocalNotices())
              }
              Text('刷新').fontColor(this.palette().primary).fontSize(11).margin({ left: 14 }).onClick(() => this.onLocalNoticesChanged())
            }.width('100%')
            Row({ space: 7 }) {
              this.FilterChip('全部', null)
              this.FilterChip('微信', NotificationSource.WECHAT)
              this.FilterChip('企业微信', NotificationSource.WECOM)
              this.FilterChip('QQ', NotificationSource.QQ)
              this.FilterChip('学习通', NotificationSource.XUEXITONG)
            }.width('100%')
            Column() {
              if (this.visibleLocalNotices().length === 0) {
                Text(this.localNotices.length === 0 ? '暂无本地自动收集记录' : '当前来源暂无记录').fontColor(this.palette().muted).fontSize(12).padding(30)
              } else {
                ForEach(this.visibleLocalNotices(), (item: LocalCapturedNotice, index: number) => {
                  this.LocalNoticeRow(item)
                  if (index < this.visibleLocalNotices().length - 1) { Divider().color(this.palette().line) }
                }, (item: LocalCapturedNotice) => item.id)
              }
            }.width('100%').padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
          }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
        }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
