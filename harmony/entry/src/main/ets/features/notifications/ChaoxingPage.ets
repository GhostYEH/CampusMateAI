import { promptAction } from '@kit.ArkUI';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { ChaoxingAccountStatus, ChaoxingStatusMapper } from '../../data/chaoxing/ChaoxingAccount';
import { ChaoxingRepository } from '../../data/chaoxing/ChaoxingRepository';

@Component
export struct ChaoxingPage {
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State account: ChaoxingAccountStatus = ChaoxingStatusMapper.unavailable();
  @State checking: boolean = true;
  @State username: string = '';
  @State password: string = '';
  @State submitting: boolean = false;
  @State syncing: boolean = false;
  @State disconnecting: boolean = false;
  @State message: string = '';
  repository: ChaoxingRepository | null = null;
  onBack: () => void = () => {};
  onStatusChanged: (status: ChaoxingAccountStatus) => void = () => {};
  onSynced: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void { this.refreshStatus(); }

  async refreshStatus(): Promise<void> {
    if (this.repository === null) return;
    this.checking = true;
    try {
      this.account = await this.repository.getStatus();
      this.onStatusChanged(this.account);
    } catch (e) {
      this.account = ChaoxingStatusMapper.unavailable();
      this.message = (e as Error).message;
    } finally {
      this.checking = false;
    }
  }

  async login(): Promise<void> {
    if (this.repository === null || this.username.trim().length === 0 || this.password.length === 0) return;
    this.submitting = true;
    this.message = '';
    try {
      await this.repository.login(this.username.trim(), this.password);
      this.password = '';
      this.message = '连接成功';
      await this.refreshStatus();
    } catch (e) {
      this.message = (e as Error).message;
    } finally {
      this.submitting = false;
    }
  }

  async syncNow(): Promise<void> {
    if (this.repository === null || !this.account.canSync || this.syncing) return;
    this.syncing = true;
    this.message = '';
    try {
      await this.repository.sync();
      this.message = '同步成功';
      await this.refreshStatus();
      this.onSynced();
    } catch (e) {
      this.message = (e as Error).message;
    } finally {
      this.syncing = false;
    }
  }

  confirmDisconnect(): void {
    promptAction.showDialog({
      title: '断开学习通',
      message: '断开后将停止从学习通导入课程、作业和通知。',
      buttons: [{ text: '取消', color: this.palette().muted }, { text: '断开', color: this.palette().danger }]
    }).then((result: promptAction.ShowDialogSuccessResponse) => {
      if (result.index === 1) this.disconnect();
    }).catch(() => {});
  }

  async disconnect(): Promise<void> {
    if (this.repository === null || this.disconnecting) return;
    this.disconnecting = true;
    try {
      await this.repository.disconnect();
      this.account = ChaoxingStatusMapper.fromResponse({ status: 'offline' });
      this.onStatusChanged(this.account);
      this.message = '已断开学习通';
    } catch (e) {
      this.message = (e as Error).message;
    } finally {
      this.disconnecting = false;
    }
  }

  build() {
    Column() {
      SecondaryHeader({ title: '学习通', subtitle: '连接账号并同步课程内容', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: this.onBack })
      Scroll() {
        Column({ space: 14 }) {
          Column({ space: 12 }) {
            Row({ space: 12 }) {
              Stack({ alignContent: Alignment.Center }) {
                SymbolGlyph($r('sys.symbol.book')).fontSize(22).fontColor([this.palette().primary])
              }.width(46).height(46).backgroundColor(this.palette().soft).borderRadius(14)
              Column({ space: 4 }) {
                Text('学习通连接').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold)
                Text(this.checking ? '正在检查连接…' : this.account.label)
                  .fontColor(this.account.connected ? this.palette().success : this.palette().muted).fontSize(12)
              }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            }.width('100%')
            if (this.account.connected) {
              Text(this.account.summary).fontColor(this.palette().text).fontSize(13).width('100%')
              Text(this.account.lastSyncedAt.length > 0 ? `上次同步：${this.account.lastSyncedAt}` : '尚未完成首次同步')
                .fontColor(this.palette().muted).fontSize(11).width('100%')
            } else if (!this.checking) {
              Text(this.account.rawStatus === 'expired' ? '学习通登录已失效，请重新登录后继续同步。' : '连接后可导入课程、作业与课程通知。')
                .fontColor(this.palette().muted).fontSize(12).lineHeight(19).width('100%')
            }
          }.width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)

          if (!this.account.connected && !this.checking) {
            Column({ space: 12 }) {
              Text('学习通账号登录').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold).width('100%')
              Text('仅用于连接学习通，本地不会保存你的密码。').fontColor(this.palette().muted).fontSize(11).width('100%')
              TextInput({ text: this.username, placeholder: '手机号或学习通账号' })
                .width('100%').height(44).fontSize(13).fontColor(this.palette().text).backgroundColor(this.palette().background).borderRadius(11)
                .onChange((value: string) => this.username = value)
              TextInput({ text: this.password, placeholder: '密码' })
                .type(InputType.Password).width('100%').height(44).fontSize(13).fontColor(this.palette().text)
                .backgroundColor(this.palette().background).borderRadius(11).onChange((value: string) => this.password = value)
              Button(this.submitting ? '连接中…' : '连接学习通').width('100%').height(44).borderRadius(11)
                .backgroundColor(this.palette().primary).fontColor('#FFFFFFFF')
                .enabled(!this.submitting && this.username.trim().length > 0 && this.password.length > 0).onClick(() => this.login())
            }.width('100%').padding(16).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).borderRadius(18)
          }

          if (this.account.connected) {
            Column({ space: 10 }) {
              Button(this.syncing ? '同步中…' : '立即同步').width('100%').height(44).borderRadius(11)
                .backgroundColor(this.palette().primary).fontColor('#FFFFFFFF').enabled(!this.syncing).onClick(() => this.syncNow())
              Button(this.disconnecting ? '断开中…' : '断开连接').width('100%').height(42).borderRadius(11)
                .backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 }).fontColor(this.palette().danger).border({ width: 1, color: this.palette().glass.border })
                .enabled(!this.disconnecting && !this.syncing).onClick(() => this.confirmDisconnect())
            }.width('100%')
          }

          if (this.message.length > 0) {
            Text(this.message).width('100%').padding(12).borderRadius(12).backgroundColor(this.palette().soft)
              .fontColor(this.palette().text).fontSize(12).textAlign(TextAlign.Center)
          }
        }.width('100%').padding({ left: 14, right: 14, bottom: 28 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
