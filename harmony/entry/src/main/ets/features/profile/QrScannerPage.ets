import { common } from '@kit.AbilityKit';
import { scanBarcode, scanCore } from '@kit.ScanKit';
import { QrPayload, parseQrPayload } from '../../data/QrPayloadParser';
import { ApiClient, QrScanResult } from '../../data/ApiClient';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

@Component
export struct QrScannerPage {
  @Prop darkMode: boolean = false;
  apiClient: ApiClient | null = null;
  onBack: () => void = () => {};
  onScanned: (sessionId: string, scanToken: string, browserName: string, osName: string, deviceLabel: string) => void = () => {};
  @State errorMessage: string = '';
  @State scanning: boolean = true;
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void {
    this.startScan();
  }

  async startScan(): Promise<void> {
    try {
      const context: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
      const options: scanBarcode.ScanOptions = {
        scanTypes: [scanCore.ScanType.QR_CODE],
        enableMultiMode: false,
        enableAlbum: false,
      };
      const result: scanBarcode.ScanResult = await scanBarcode.startScanForResult(context, options);
      const rawValue: string = result.originalValue;
      const parsed: QrPayload | null = parseQrPayload(rawValue);
      if (parsed === null) {
        this.errorMessage = '不是有效的 CampusMate 登录二维码';
        this.scanning = false;
        return;
      }
      // 调用 /auth/qr/scan
      if (this.apiClient === null) {
        this.errorMessage = 'API 客户端未初始化';
        this.scanning = false;
        return;
      }
      const scanResult: QrScanResult = await this.apiClient.qrScan(parsed.sessionId, parsed.scanToken);
      this.onScanned(
        scanResult.session_id,
        parsed.scanToken,
        scanResult.browser_name ?? '',
        scanResult.os_name ?? '',
        scanResult.device_label ?? '',
      );
    } catch (e) {
      // 用户取消扫码或扫码失败
      this.scanning = false;
      const msg: string = (e as Error)?.message ?? '';
      if (msg.includes('cancel') || msg.includes('Cancel')) {
        this.onBack();
      } else {
        this.errorMessage = msg || '扫码失败，请重试';
      }
    }
  }

  build() {
    Column() {
      // 顶部导航
      Row() {
        Button() {
          SymbolGlyph($r('sys.symbol.chevron_left')).fontSize(22).fontColor([this.palette().text])
        }.type(ButtonType.Normal).backgroundColor(Color.Transparent).onClick(() => this.onBack())
        Text('扫一扫').fontColor(this.palette().text).fontSize(18).fontWeight(FontWeight.Bold).margin({ left: 8 })
      }.width('100%').height(56).padding({ left: 12, right: 12 }).alignItems(VerticalAlign.Center)

      Column({ space: 16 }) {
        if (this.errorMessage.length > 0) {
          Text(this.errorMessage).fontColor('#FFF2674F').fontSize(15).textAlign(TextAlign.Center)
          Button() {
            Text('重新扫码').fontColor(Color.White).fontSize(15)
          }.type(ButtonType.Capsule).backgroundColor(this.palette().primary).onClick(() => {
            this.errorMessage = '';
            this.scanning = true;
            this.startScan();
          })
        } else {
          Column({ space: 12 }) {
            LoadingProgress().width(48).height(48).color(this.palette().primary)
            Text('正在调起扫码…').fontColor(this.palette().muted).fontSize(14)
          }
        }
      }.layoutWeight(1).width('100%').justifyContent(FlexAlign.Center)

      Text('将二维码放入框内，即可自动扫描').fontColor(this.palette().muted).fontSize(13).margin({ bottom: 48 })
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}