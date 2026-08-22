import { ApiClient, QrConfirmResult } from '../../data/ApiClient';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

@Component
export struct QrConfirmPage {
  @Prop darkMode: boolean = false;
  @Prop sessionId: string = '';
  @Prop scanToken: string = '';
  @Prop browserName: string = '';
  @Prop osName: string = '';
  @Prop deviceLabel: string = '';
  apiClient: ApiClient | null = null;
  onBack: () => void = () => {};
  onSuccess: () => void = () => {};
  @State trustDevice: boolean = false;
  @State loading: boolean = false;
  @State errorMessage: string = '';
  @State success: boolean = false;
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  get deviceText(): string {
    if (this.deviceLabel.length > 0) return this.deviceLabel;
    const parts: string[] = [];
    if (this.browserName.length > 0) parts.push(this.browserName);
    if (this.osName.length > 0) parts.push(this.osName);
    return parts.length > 0 ? parts.join(' · ') : 'Web 浏览器';
  }

  async doConfirm(): Promise<void> {
    if (this.loading) return;
    this.loading = true;
    this.errorMessage = '';
    try {
      if (this.apiClient === null) {
        this.errorMessage = 'API 客户端未初始化';
        this.loading = false;
        return;
      }
      const result: QrConfirmResult = await this.apiClient.qrConfirm(this.sessionId, this.scanToken, this.trustDevice);
      this.success = true;
      this.loading = false;
      setTimeout(() => { this.onSuccess(); }, 1500);
    } catch (e) {
      const msg: string = (e as Error)?.message ?? '';
      if (msg.includes('QR_USER_MISMATCH')) this.errorMessage = '确认用户与扫描用户不一致';
      else if (msg.includes('QR_EXPIRED')) this.errorMessage = '二维码已过期';
      else if (msg.includes('QR_ALREADY_CONFIRMED')) this.errorMessage = '二维码已确认';
      else if (msg.includes('QR_CANCELLED')) this.errorMessage = '二维码已取消';
      else this.errorMessage = msg || '确认失败，请重试';
      this.loading = false;
    }
  }

  async doCancel(): Promise<void> {
    if (this.loading) return;
    try {
      if (this.apiClient !== null) await this.apiClient.qrCancel(this.sessionId, this.scanToken);
    } catch (_e) { /* 忽略取消失败 */ }
    this.onBack();
  }

  build() {
    Column() {
      // 顶部导航
      Row() {
        Button() {
          SymbolGlyph($r('sys.symbol.chevron_left')).fontSize(22).fontColor([this.palette().text])
        }.type(ButtonType.Normal).backgroundColor(Color.Transparent).enabled(!this.loading).onClick(() => this.onBack())
        Text('确认登录').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold).margin({ left: 8 })
      }.width('100%').height(56).padding({ left: 12, right: 12 }).alignItems(VerticalAlign.Center)

      if (this.success) {
        Column({ space: 16 }) {
          Stack({ alignContent: Alignment.Center }) {
            SymbolGlyph($r('sys.symbol.computer')).fontSize(36).fontColor([this.palette().success])
          }.width(72).height(72).backgroundColor('#1F31AE91').borderRadius(36)
          Text('已确认登录').fontColor(this.palette().text).fontSize(20).fontWeight(FontWeight.Bold)
          Text('请在 Web 端查看').fontColor(this.palette().muted).fontSize(14)
        }.layoutWeight(1).width('100%').justifyContent(FlexAlign.Center)
      } else {
        Column({ space: 0 }) {
          Blank().layoutWeight(1)
          // 中央电脑图标
          Stack({ alignContent: Alignment.Center }) {
            SymbolGlyph($r('sys.symbol.computer')).fontSize(44).fontColor(['#FFFFFFFF'])
          }.width(88).height(88).borderRadius(44).linearGradient({ angle: 90, colors: [['#FF4E5EDB', 0], ['#FF5B68F2', 1]] })

          Text('登录 CampusMate Web').fontColor(this.palette().text).fontSize(22).fontWeight(FontWeight.Bold).margin({ top: 24 })
          Text(this.deviceText).fontColor(this.palette().primary).fontSize(16).fontWeight(FontWeight.Medium).margin({ top: 12 })
          Text('请确认是你本人在此设备上操作').fontColor(this.palette().muted).fontSize(14).margin({ top: 8 })

          Blank().layoutWeight(1)

          // 信任设备复选框
          Row() {
            Checkbox({ name: 'trust', group: 'trustGroup' })
              .select(this.trustDevice)
              .selectedColor(this.palette().primary)
              .onChange((value: boolean) => { this.trustDevice = value; })
            Text('信任当前设备自动登录').fontColor(this.palette().text).fontSize(14).margin({ left: 8 })
          }.width('100%').padding({ top: 8, bottom: 8 }).onClick(() => { this.trustDevice = !this.trustDevice; })

          if (this.errorMessage.length > 0) {
            Text(this.errorMessage).fontColor('#FFF2674F').fontSize(13).margin({ top: 4 })
          }

          // 主按钮
          Button() {
            Text(this.loading ? '正在确认…' : '登录 Web 端').fontColor(Color.White).fontSize(16).fontWeight(FontWeight.Bold)
          }.width('100%').height(50).type(ButtonType.Capsule).backgroundColor(this.palette().primary)
            .enabled(!this.loading).margin({ top: 12 }).onClick(() => this.doConfirm())

          // 取消按钮
          Button() {
            Text('取消').fontColor(this.palette().muted).fontSize(15)
          }.width('100%').type(ButtonType.Normal).backgroundColor(Color.Transparent)
            .enabled(!this.loading).margin({ top: 8 }).onClick(() => this.doCancel())
        }.width('100%').height('100%').padding({ left: 28, right: 28, bottom: 32 })
      }
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}