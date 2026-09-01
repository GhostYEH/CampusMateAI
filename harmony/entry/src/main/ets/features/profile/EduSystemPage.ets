import { EduRepository, eduStateText, eduStateTextWithErrorCode } from '../../repository/EduRepository';
import { EduBindingDto, EduConnectionDto, EduPreLoginResult, EduProbeResult, EduScheduleItemsResponse, EduSyncResult } from '../../data/ApiClient';
import { CampusPalette, lightPalette, darkPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { ApiClient } from '../../data/ApiClient';
import { promptAction } from '@kit.ArkUI';
import { resolveEduLoginUrl } from '../edu/EduLoginSecurity';

/** EduSystemPage — 教务系统连接主页（完整闭环）。

 * 地址输入 → 探测 → 创建连接 → 分流（backend_http / client_webview）→ 连接管理。
 */
@Component
export struct EduSystemPage {
  @Prop darkMode: boolean = false;
  @Prop universityId: string = '';
  @Prop apiBaseUrl: string = '';
  @Prop authToken: string = '';
  @Prop apiClient: ApiClient = new ApiClient('', () => '', null);
  @State portalUrl: string = '';
  @State username: string = '';
  @State password: string = '';
  @State captchaInput: string = '';
  @State preLoginResult: EduPreLoginResult | null = null;
  @State loading: boolean = false;
  @State errorMsg: string = '';
  @State infoMsg: string = '';
  @State binding: EduBindingDto | null = null;
  @State connection: EduConnectionDto | null = null;
  @State probe: EduProbeResult | null = null;
  @State syncing: boolean = false;
  @State syncMsg: string = '';
  @State polling: boolean = false;
  private pollTimer: number = -1;

  onBack: () => void = () => {};
  onNavigateToLogin: (loginUrl: string, connectionId: string, allowedOrigins: string[]) => void = () => {};
  onOpenSchedule: () => void = () => {};

  palette(): CampusPalette {
    return this.darkMode ? darkPalette : lightPalette;
  }

  buildClient(): ApiClient {
    return this.apiClient;
  }

  async aboutToAppear() {
    await this.loadBinding();
  }

  aboutToDisappear() {
    this.stopPolling();
  }

  async loadBinding() {
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      this.binding = await repo.getBinding() || null;
    } catch (e) {
      // 忽略初始加载错误
    }
  }

  async probeAndConnect() {
    const url = this.portalUrl.trim();
    if (url.length === 0) return;
    this.loading = true;
    this.errorMsg = '';
    this.infoMsg = '';
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      const conn = await repo.createConnectionFromUrl(url, this.universityId || undefined);
      this.connection = conn;
      this.probe = { portal_url: url, provider: conn.provider, provider_confidence: 0, reachable: true, is_edu_page: true, suggested_login_mode: conn.login_execution_mode, evidence: [] } as EduProbeResult;
      if (conn.login_execution_mode === 'client_webview') {
        this.infoMsg = '该教务系统需要在客户端浏览器中由您本人完成登录。';
        this.startPolling(conn.id);
      } else if (conn.login_execution_mode === 'backend_http') {
        this.infoMsg = '该教务系统支持账号密码登录。';
      }
    } catch (e) {
      this.errorMsg = String(e).substring(0, 150);
    } finally {
      this.loading = false;
    }
  }

  async submitCredentials() {
    if (this.connection === null || this.username.length === 0 || this.password.length === 0) return;
    this.loading = true;
    this.errorMsg = '';
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      const conn = await repo.continueWithCredentials(this.connection.id, this.username, this.password);
      this.connection = conn;
      const loginUrl: string | undefined = resolveEduLoginUrl(conn.portal_url, this.portalUrl);
      if (conn.state === 'connected') {
        await this.onConnected();
      } else if (conn.state === 'waiting_user_login' && conn.error_code === 'NEED_CAPTCHA') {
        await this.fetchCaptchaImage();
      } else if (conn.state === 'waiting_user_login' && loginUrl !== undefined) {
        this.infoMsg = eduStateTextWithErrorCode(conn.state, conn.error_code);
        this.onNavigateToLogin(loginUrl, conn.id, conn.allowed_origins || []);
        this.startPolling(conn.id);
      } else if (conn.state === 'auth_failed') {
        this.errorMsg = conn.error_message || '账号或密码错误';
      } else {
        this.errorMsg = conn.error_message || '登录失败';
      }
    } catch (e) {
      this.errorMsg = String(e).substring(0, 150);
    } finally {
      this.loading = false;
    }
  }

  async fetchCaptchaImage() {
    if (this.connection === null) return;
    this.loading = true;
    this.errorMsg = '';
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      this.preLoginResult = await repo.preLogin(this.connection.id);
      if (!this.preLoginResult.captcha_required || !this.preLoginResult.captcha_image_base64) {
        this.errorMsg = '无法获取验证码图片，请尝试在浏览器中完成登录';
      }
    } catch (e) {
      this.errorMsg = String(e).substring(0, 150);
    } finally {
      this.loading = false;
    }
  }

  async submitCredentialsWithCaptcha() {
    if (this.connection === null || this.preLoginResult === null || this.captchaInput.length === 0) return;
    this.loading = true;
    this.errorMsg = '';
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      const conn = await repo.continueWithCaptcha(
        this.connection.id, this.username, this.password, this.captchaInput, this.preLoginResult.pre_login_token
      );
      this.connection = conn;
      this.preLoginResult = null;
      this.captchaInput = '';
      if (conn.state === 'connected') {
        await this.onConnected();
      } else if (conn.state === 'waiting_user_login' && conn.error_code === 'NEED_CAPTCHA') {
        await this.fetchCaptchaImage();
      } else if (conn.state === 'auth_failed') {
        this.errorMsg = conn.error_message || '账号或密码错误';
      } else {
        this.errorMsg = conn.error_message || '登录失败';
      }
    } catch (e) {
      this.errorMsg = String(e).substring(0, 150);
    } finally {
      this.loading = false;
    }
  }

  async refreshCaptcha() {
    this.captchaInput = '';
    await this.fetchCaptchaImage();
  }

  startPolling(connId: string) {
    this.stopPolling();
    this.polling = true;
    let count = 0;
    const poll = async () => {
      count++;
      if (count > 60 || !this.polling) { this.stopPolling(); return; }
      try {
        const client = this.buildClient();
        const repo = new EduRepository(client);
        const conn = await repo.pollConnection(connId);
        this.connection = conn;
        if (conn.state === 'connected') {
          this.stopPolling();
          await this.onConnected();
        } else if (conn.state === 'waiting_user_login' && conn.error_code === 'NEED_CAPTCHA') {
          this.stopPolling();
          await this.fetchCaptchaImage();
        }
      } catch { /* ignore poll error */ }
    };
    this.pollTimer = setInterval(poll, 3000);
  }

  stopPolling() {
    this.polling = false;
    if (this.pollTimer !== -1) { clearInterval(this.pollTimer); this.pollTimer = -1; }
  }

  async onConnected() {
    this.infoMsg = '教务系统连接成功';
    await this.loadBinding();
    await this.autoSync();
  }

  async autoSync() {
    this.syncing = true;
    this.syncMsg = '正在同步课表…';
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      const schedResult = await repo.syncSchedule();
      const storedSchedule: EduScheduleItemsResponse = await repo.listScheduleItems(
        schedResult.schedule?.semester || schedResult.semester
      );
      this.syncMsg = '正在同步成绩…';
      const gradeResult = await repo.syncGrade();
      this.syncMsg = '正在同步考试安排…';
      const examResult = await repo.syncExam();
      const schedOk = schedResult.status === 'success' && schedResult.persisted === true &&
        schedResult.items_count > 0 && storedSchedule.items_count > 0;
      const gradeOk = gradeResult.status === 'success';
      const examOk = examResult.status === 'success';
      this.syncMsg = `课表同步${schedOk ? '成功' : '失败'}，成绩同步${gradeOk ? '成功' : '失败'}，考试同步${examOk ? '成功' : '失败'}`;
      await this.loadBinding();
    } catch (e) {
      this.syncMsg = '同步失败: ' + String(e).substring(0, 100);
    } finally {
      this.syncing = false;
    }
  }

  async disconnect() {
    this.loading = true;
    try {
      const client = this.buildClient();
      const repo = new EduRepository(client);
      await repo.unbind();
      this.binding = null;
      this.connection = null;
      this.probe = null;
      this.infoMsg = '已断开教务系统连接';
    } catch (e) {
      this.errorMsg = String(e).substring(0, 150);
    } finally {
      this.loading = false;
    }
  }

  confirmDisconnect() {
    promptAction.showDialog({
      title: '断开教务系统',
      message: '断开后将停止自动同步，但已经同步的数据不会立即删除。',
      buttons: [
        { text: '确认断开', color: this.palette().danger },
        { text: '取消', color: this.palette().muted }
      ]
    }).then((res: promptAction.ShowDialogSuccessResponse) => {
      if (res.index === 0) {
        this.disconnect();
      }
    }).catch(() => {});
  }

  build() {
    Column({ space: 0 }) {
      SecondaryHeader({ title: '教务系统', subtitle: '连接教务系统，同步课表与成绩', darkMode: this.darkMode, onBack: () => this.onBack() })

      Scroll() {
        Column({ space: 12 }) {
          if (this.universityId.length === 0) {
            Column({ space: 6 }) {
              Text('请先选择你的大学').fontSize(15).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
              Text('教务系统连接需要先在个人中心选择所在大学。').fontSize(12).fontColor(this.palette().muted)
            }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
          } else if (this.binding !== null && (this.binding.connection_status === 'active' || this.binding.connection_status === 'connected')) {
            this.ConnectedCard()
          } else {
            this.PortalInputCard()
            if (this.probe !== null) {
              this.ProbeResultCard()
            }
            if (this.connection !== null && this.connection.login_execution_mode === 'backend_http') {
              this.CredentialFormCard()
            }
            if (this.preLoginResult !== null) {
              this.CaptchaFormCard()
            }
            if (this.connection !== null && this.connection.login_execution_mode === 'client_webview') {
              Button('打开教务登录页面')
                .width('90%').height(44)
                .backgroundColor(this.palette().primary).fontColor(Color.White)
                .onClick(() => {
                  if (this.connection !== null) {
                    const loginUrl: string | undefined = resolveEduLoginUrl(this.connection.portal_url, this.portalUrl);
                    if (loginUrl !== undefined) {
                      this.onNavigateToLogin(loginUrl, this.connection.id, this.connection.allowed_origins || []);
                    }
                  }
                })
            }
          }

          if (this.errorMsg.length > 0) {
            Text(this.errorMsg).fontSize(12).fontColor(this.palette().danger).padding(16)
          }
          if (this.infoMsg.length > 0) {
            Text(this.infoMsg).fontSize(13).fontColor(this.palette().success).padding(16)
          }
          if (this.syncing) {
            Row({ space: 8 }) {
              LoadingProgress().width(20).height(20).color(this.palette().primary)
              Text(this.syncMsg).fontSize(13).fontColor(this.palette().muted)
            }.padding(16)
          }
        }.width('100%').padding(16)
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)

  }

  @Builder PortalInputCard() {
    Column({ space: 8 }) {
      Text('连接教务系统').fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Text('输入高校教务系统网址，CampusMate 将自动识别系统类型。').fontSize(12).fontColor(this.palette().muted)
      TextInput({ text: this.portalUrl, placeholder: 'https://jwxt.yourschool.edu.cn/' })
        .width('100%').height(44)
        .onChange((value: string) => { this.portalUrl = value; })
        .enabled(!this.loading)
      Button(this.loading ? '检测中…' : '检测教务系统')
        .width('100%').height(44)
        .backgroundColor(this.palette().primary).fontColor(Color.White)
        .enabled(!this.loading && this.portalUrl.trim().length > 0)
        .onClick(() => this.probeAndConnect())
    }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
  }

  @Builder ProbeResultCard() {
    Column({ space: 4 }) {
      Text('已识别').fontSize(15).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      if (this.probe !== null && this.probe.title !== undefined) {
        Text('页面：' + (this.probe.title || '')).fontSize(12).fontColor(this.palette().muted)
      }
      if (this.probe !== null) {
        Text('系统厂商：' + this.probe.provider).fontSize(12).fontColor(this.palette().muted)
        Text('登录方式：' + (this.probe.suggested_login_mode === 'client_webview' ? '客户端浏览器登录' : '账号密码登录')).fontSize(12).fontColor(this.palette().muted)
      }
    }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
  }

  @Builder CredentialFormCard() {
    Column({ space: 8 }) {
      Text('账号密码登录').fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      TextInput({ text: this.username, placeholder: '学号' })
        .width('100%').height(44)
        .onChange((value: string) => { this.username = value; })
        .enabled(!this.loading)
      TextInput({ text: this.password, placeholder: '密码' })
        .width('100%').height(44).type(InputType.Password)
        .onChange((value: string) => { this.password = value; })
        .enabled(!this.loading)
      Button(this.loading ? '验证中…' : '登录')
        .width('100%').height(44)
        .backgroundColor(this.palette().primary).fontColor(Color.White)
        .enabled(!this.loading && this.username.length > 0 && this.password.length > 0)
        .onClick(() => this.submitCredentials())
      Text('密码仅用于本次登录校验，不会明文保存。').fontSize(11).fontColor(this.palette().muted)
    }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
  }

  @Builder CaptchaFormCard() {
    Column({ space: 8 }) {
      Text('请输入验证码').fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Text('学校登录页要求完成图片验证码，请对照下方图片输入。').fontSize(12).fontColor(this.palette().muted)
      if (this.preLoginResult !== null && this.preLoginResult.captcha_image_base64 !== undefined && this.preLoginResult.captcha_image_base64.length > 0) {
        Row({ space: 8 }) {
          Image('data:image/png;base64,' + this.preLoginResult.captcha_image_base64)
            .width(120).height(48).objectFit(ImageFit.Contain)
          Button('换一张').backgroundColor(this.palette().surface).fontColor(this.palette().text)
            .onClick(() => this.refreshCaptcha())
        }.width('100%')
      } else {
        Text('⚠ 未获取到验证码图片，请点击换一张').fontSize(12).fontColor(this.palette().danger)
      }
      TextInput({ text: this.username, placeholder: '学号' })
        .width('100%').height(44)
        .onChange((value: string) => { this.username = value; })
        .enabled(!this.loading)
      TextInput({ text: this.password, placeholder: '密码' })
        .width('100%').height(44).type(InputType.Password)
        .onChange((value: string) => { this.password = value; })
        .enabled(!this.loading)
      TextInput({ text: this.captchaInput, placeholder: '验证码' })
        .width('100%').height(44)
        .onChange((value: string) => { this.captchaInput = value; })
        .enabled(!this.loading)
      Button(this.loading ? '验证中…' : '登录')
        .width('100%').height(44)
        .backgroundColor(this.palette().primary).fontColor(Color.White)
        .enabled(!this.loading && this.username.length > 0 && this.password.length > 0 && this.captchaInput.length > 0)
        .onClick(() => this.submitCredentialsWithCaptcha())
      Text('密码仅用于本次登录校验，不会明文保存。').fontSize(11).fontColor(this.palette().muted)
    }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
  }

  @Builder ConnectedCard() {
    Column({ space: 6 }) {
      if (this.binding !== null) {
        Text(this.binding.provider).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
        Text('状态：' + eduStateText(this.binding.connection_status)).fontSize(12).fontColor(this.palette().muted)
        if (this.binding.external_student_id !== undefined) {
          Text('学号：' + (this.binding.external_student_id || '')).fontSize(12).fontColor(this.palette().muted)
        }
        if (this.binding.last_synced_at !== undefined) {
          Text('最后同步：' + (this.binding.last_synced_at || '')).fontSize(12).fontColor(this.palette().muted)
        }
        if (this.binding.last_error !== undefined && (this.binding.last_error || '').length > 0) {
          Text('错误：' + (this.binding.last_error || '')).fontSize(12).fontColor(this.palette().danger)
        }
      }
      Blank().height(8)
      if (this.syncing) {
        LoadingProgress().width(20).height(20).color(this.palette().primary)
        Text(this.syncMsg).fontSize(12).fontColor(this.palette().muted)
      } else {
        Row({ space: 8 }) {
          Button('立即同步').backgroundColor(this.palette().primary).fontColor(Color.White).onClick(() => this.autoSync())
          Button('重新登录').backgroundColor(this.palette().surface).fontColor(this.palette().text).onClick(() => {
            this.binding = null;
            this.connection = null;
            this.probe = null;
            this.portalUrl = '';
          })
          Button('断开').backgroundColor(this.palette().surface).fontColor(this.palette().danger).onClick(() => {
            this.confirmDisconnect();
          })
        }
        Button('查看课表').width('100%').height(40).backgroundColor(this.palette().surface).fontColor(this.palette().primary)
          .margin({ top: 8 }).onClick(() => this.onOpenSchedule())
      }
    }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
  }
}
