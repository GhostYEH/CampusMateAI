import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

export interface EduSystemInfo {
  id: string;
  system_key: string;
  name: string | null;
  provider: string;
  status: string;
  is_mock: boolean;
  login_execution_mode: string;
  supported_features: string[];
}

export function eduStateText(state: string): string {
  const map: Record<string, string> = {
    'idle': '未连接',
    'connecting': '连接中…',
    'auth_required': '需要登录验证',
    'waiting_user_login': '等待用户登录',
    'need_captcha': '学校要求完成人机验证',
    'need_slider': '需要完成滑块验证',
    'need_sms': '需要短信验证码',
    'need_mfa': '需要多因素认证',
    'need_user_action': '需要用户操作',
    'authenticated': '已认证',
    'syncing': '同步中…',
    'connected': '已连接',
    'session_expired': '登录状态已过期，请重新验证',
    'auth_failed': '认证失败',
    'network_error': '网络错误',
    'system_unavailable': '教务系统暂不可用',
    'unsupported': '该教务系统暂未完成适配',
    'error': '连接出错',
    'active': '已连接',
    'unbound': '未绑定',
  };
  return map[state] || state;
}

@Component
export struct EduSystemPage {
  @Prop darkMode: boolean = false;
  @Prop universityId: string = '';
  @Prop universityName: string = '';
  @State systems: EduSystemInfo[] = [];
  @State loading: boolean = true;
  @State errorText: string = '';
  onBack: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear() {
    this.loadSystems();
  }

  async loadSystems() {
    if (!this.universityId) {
      this.loading = false;
      return;
    }
    this.loading = true;
    try {
      const token = AppStorage.get<string>('auth_token') || '';
      const resp = await fetch(`${AppStorage.get<string>('api_base') || ''}/api/v1/edu/systems/${this.universityId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (resp.ok) {
        this.systems = await resp.json() as EduSystemInfo[];
      } else {
        this.errorText = '加载失败';
      }
    } catch (e) {
      this.errorText = '网络错误';
    } finally {
      this.loading = false;
    }
  }

  @Builder SystemCard(sys: EduSystemInfo) {
    Column({ space: 6 }) {
      Text(sys.name || sys.system_key)
        .fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
      Text(`厂商：${sys.provider}`)
        .fontSize(13).fontColor(this.palette().muted)
      Text(`状态：${sys.status}`)
        .fontSize(13).fontColor(this.palette().muted)
      Text(`登录方式：${sys.login_execution_mode}`)
        .fontSize(13).fontColor(this.palette().muted)
      if (sys.is_mock) {
        Text('⚠ Mock 数据').fontSize(13).fontColor('#E08A4E')
      }
      Row({ space: 8 }) {
        ForEach(sys.supported_features, (f: string) => {
          Text(`✓ ${f}`).fontSize(12).fontColor(this.palette().primary)
        })
      }
      Button('连接教务系统')
        .backgroundColor(this.palette().primary).fontColor(Color.White)
        .height(40).borderRadius(12)
    }
    .width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
  }

  build() {
    Column({ space: 12 }) {
      Row() {
        Text('教务系统').fontSize(22).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
        Blank()
        Text('返回').fontSize(15).fontColor(this.palette().primary).onClick(() => this.onBack())
      }.width('100%')

      if (this.universityName) {
        Text(this.universityName).fontSize(16).fontColor(this.palette().text)
      }

      if (this.loading) {
        Column() {
          LoadingProgress().width(40).height(40)
        }.width('100%').height(200).justifyContent(FlexAlign.Center)
      } else if (this.errorText) {
        Text(this.errorText).fontColor(this.palette().muted)
      } else if (this.systems.length === 0) {
        Column({ space: 8 }) {
          Text('暂未收录该校教务系统').fontSize(16).fontWeight(FontWeight.Bold)
          Text('你仍可继续使用手动课程表和其他 CampusMate 功能。').fontSize(13).fontColor(this.palette().muted)
        }.width('100%').padding(16).backgroundColor(this.palette().surface).borderRadius(16)
      } else {
        Scroll() {
          Column({ space: 10 }) {
            ForEach(this.systems, (sys: EduSystemInfo) => {
              this.SystemCard(sys)
            })
          }
        }.layoutWeight(1)
      }
    }
    .width('100%').height('100%').padding(16)
  }
}