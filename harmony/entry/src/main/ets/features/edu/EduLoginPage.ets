import { webview } from '@kit.ArkWeb';
import { EduRepository } from '../../repository/EduRepository';
import { EduCookieDto } from '../../data/EduCookieDto';
import { CampusPalette, lightPalette, darkPalette } from '../../ui/Theme';
import { ApiClient } from '../../data/ApiClient';
import { cookieDtosForUrl, isAllowedEduNavigation } from './EduLoginSecurity';

interface PageEndEvent { url: string }
interface UrlLoadEvent { data: string | WebResourceRequest }

/** EduLoginPage — ArkWeb 内嵌教务登录页。

 * 用户在 Web 组件中完成学校官方登录；
 * onPageEnd 时自动检测 + 提供"我已完成登录"按钮兜底；
 * 登录成功后提取 Cookie 回传后端验证。
 */
@Component
export struct EduLoginPage {
  @Prop darkMode: boolean = false;
  @Prop loginUrl: string = '';
  @Prop connectionId: string = '';
  @Prop apiBaseUrl: string = '';
  @Prop authToken: string = '';
  @Prop backendAllowedOrigins: string[] = [];
  @State currentUrl: string = '';
  @State verifying: boolean = false;
  @State errorMsg: string = '';
  @State connected: boolean = false;
  @State lastVerifyTime: number = 0;
  private controller: webview.WebviewController = new webview.WebviewController();
  onBack: () => void = () => {};
  onConnected: () => void = () => {};

  private clearSensitiveLoginState(): void {
    this.currentUrl = '';
    this.errorMsg = '';
    this.verifying = false;
    try { webview.WebCookieManager.clearAllCookiesSync(); } catch (_) {}
    try { this.controller.clearHistory(); } catch (_) {}
    try { this.controller.removeCache(true); } catch (_) {}
    try { this.controller.loadUrl('about:blank'); } catch (_) {}
  }

  aboutToDisappear(): void {
    this.clearSensitiveLoginState();
  }

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  async tryVerifyLogin(url: string): Promise<void> {
    if (url.length === 0 || this.verifying) return;
    const now = Date.now();
    if (now - this.lastVerifyTime < 1200) return;
    this.lastVerifyTime = now;
    try {
      if (!isAllowedEduNavigation(url, this.loginUrl, this.backendAllowedOrigins)) return;
      const urlsToCheck = [url, this.currentUrl, this.loginUrl].filter((u) => u.length > 0);
      const cookieJar: EduCookieDto[] = [];
      for (const u of urlsToCheck) {
        if (!isAllowedEduNavigation(u, this.loginUrl, this.backendAllowedOrigins)) continue;
        try {
          const cs = await webview.WebCookieManager.fetchCookie(u);
          if (cs.length > 0) {
            cookieJar.push(...cookieDtosForUrl(cs, u));
          }
        } catch { /* 忽略单个 URL 的 cookie 获取失败 */ }
      }
      if (cookieJar.length === 0) return;
      this.verifying = true;
      const client = new ApiClient(this.apiBaseUrl, () => this.authToken, null);
      const repo = new EduRepository(client);
      const conn = await repo.continueWithCookies(this.connectionId, cookieJar, url, this.controller.getUserAgent());
      if (conn.state === 'connected') {
        this.connected = true;
        this.verifying = false;
        this.clearSensitiveLoginState();
        this.onConnected();
      } else if (conn.state === 'waiting_user_login') {
        this.errorMsg = '暂未检测到有效登录状态，请确认已进入教务系统首页';
        this.verifying = false;
      } else {
        this.errorMsg = conn.error_message || '验证失败';
        this.verifying = false;
      }
    } catch (e) {
      this.errorMsg = String(e).substring(0, 100);
      this.verifying = false;
    }
  }

  build() {
    Column({ space: 0 }) {
      Row() {
        Button('返回').onClick(() => { this.clearSensitiveLoginState(); this.onBack(); }).backgroundColor(this.palette().surface).fontColor(this.palette().text)
        Text('教务系统登录').fontSize(16).fontWeight(FontWeight.Bold).layoutWeight(1).textAlign(TextAlign.Center)
        Button('取消').onClick(() => { this.clearSensitiveLoginState(); this.onBack(); }).backgroundColor(this.palette().surface).fontColor(this.palette().text)
      }.width('100%').padding(12)

      Text('请在下方页面中完成学校教务系统的登录。CampusMate 不保存您的密码，仅在校验后使用登录会话同步课表和成绩。')
        .fontSize(12).fontColor(this.palette().muted).padding({ left: 16, right: 16, top: 4, bottom: 4 })

      Stack() {
        Web({ src: this.loginUrl, controller: this.controller })
          .domStorageAccess(true)
          .databaseAccess(true)
          .javaScriptAccess(true)
          .onUrlLoadIntercept((event?: UrlLoadEvent) => {
            if (event === undefined) return true;
            const targetUrl: string = typeof event.data === 'string'
              ? event.data
              : event.data.getRequestUrl();
            return !isAllowedEduNavigation(targetUrl, this.loginUrl, this.backendAllowedOrigins);
          })
          .onPageEnd((e: PageEndEvent) => {
            if (!isAllowedEduNavigation(e.url, this.loginUrl, this.backendAllowedOrigins)) {
              this.controller.loadUrl('about:blank');
              return;
            }
            this.currentUrl = e.url;
            this.tryVerifyLogin(e.url);
          })
          .width('100%').height('100%')

        if (this.verifying) {
          LoadingProgress().width(40).height(40).color(this.palette().primary)
        }
      }.layoutWeight(1).width('100%')

      if (this.errorMsg.length > 0) {
        Text(this.errorMsg).fontSize(12).fontColor(this.palette().danger).padding({ left: 16, right: 16, top: 4, bottom: 4 })
      }

      Button('我已完成登录')
        .width('90%').height(44).margin({ bottom: 16 })
        .backgroundColor(this.palette().primary).fontColor(Color.White)
        .enabled(!this.verifying)
        .onClick(() => {
          this.tryVerifyLogin(this.currentUrl);
        })
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}
