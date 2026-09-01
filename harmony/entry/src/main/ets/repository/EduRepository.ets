import { ApiClient, EduBindingDto, EduConnectionDto, EduConnectionContinueRequest, EduPreLoginResult, EduProbeResult, EduScheduleItemsResponse, EduGradeItemsResponse, EduExamItemsResponse, EduSyncResult } from '../data/ApiClient';
import { EduCookieDto } from '../data/EduCookieDto';

/** EduRepository — 教务系统连接层仓库。 */
export class EduRepository {
  private client: ApiClient;

  constructor(client: ApiClient) {
    this.client = client;
  }

  async getBinding(): Promise<EduBindingDto | undefined> {
    return this.client.getEduBinding();
  }

  async unbind(): Promise<void> {
    return this.client.eduUnbind();
  }

  async probePortal(portalUrl: string): Promise<EduProbeResult> {
    return this.client.eduProbe(portalUrl);
  }

  async createConnectionFromUrl(portalUrl: string, universityId?: string): Promise<EduConnectionDto> {
    return this.client.eduCreateConnectionFromUrl(portalUrl, universityId);
  }

  async getConnection(connectionId: string): Promise<EduConnectionDto> {
    return this.client.eduGetConnection(connectionId);
  }

  async continueWithCredentials(connectionId: string, username: string, password: string): Promise<EduConnectionDto> {
    const body: EduConnectionContinueRequest = { username, password };
    return this.client.eduContinueConnection(connectionId, body);
  }

  async preLogin(connectionId: string): Promise<EduPreLoginResult> {
    return this.client.eduPreLogin(connectionId);
  }

  async continueWithCaptcha(connectionId: string, username: string, password: string, captcha: string, preLoginToken: string): Promise<EduConnectionDto> {
    const body: EduConnectionContinueRequest = { username, password, captcha, pre_login_token: preLoginToken, action: 'SUBMIT_WITH_CAPTCHA' };
    return this.client.eduContinueConnection(connectionId, body);
  }

  async continueWithCookies(connectionId: string, cookieJar: EduCookieDto[], currentUrl?: string, userAgent?: string): Promise<EduConnectionDto> {
    const body: EduConnectionContinueRequest = { action: 'CLIENT_WEBVIEW_COMPLETE', cookie_jar: cookieJar, current_url: currentUrl, user_agent: userAgent };
    return this.client.eduContinueConnection(connectionId, body);
  }

  async pollConnection(connectionId: string): Promise<EduConnectionDto> {
    const body: EduConnectionContinueRequest = { action: 'POLL' };
    return this.client.eduContinueConnection(connectionId, body);
  }

  async syncSchedule(semester?: string): Promise<EduSyncResult> {
    return this.client.eduSync('schedule', semester);
  }

  async syncGrade(semester?: string): Promise<EduSyncResult> {
    return this.client.eduSync('grade', semester);
  }

  async syncExam(semester?: string): Promise<EduSyncResult> {
    return this.client.eduSync('exam', semester);
  }

  async listScheduleItems(semester?: string): Promise<EduScheduleItemsResponse> {
    return this.client.eduScheduleItems(semester);
  }

  async listGradeItems(semester?: string): Promise<EduGradeItemsResponse> {
    return this.client.eduGradeItems(semester);
  }

  async listExamItems(semester?: string): Promise<EduExamItemsResponse> {
    return this.client.eduExamItems(semester);
  }
}

/** 解析 Cookie 字符串 "k1=v1; k2=v2" 为 Map。 */
export function parseCookieString(cookieStr: string): Record<string, string> {
  const result: Record<string, string> = {};
  const parts = cookieStr.split(';');
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.length === 0) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx <= 0) continue;
    const key = trimmed.substring(0, eqIdx).trim();
    const value = trimmed.substring(eqIdx + 1).trim();
    if (key.length > 0) result[key] = value;
  }
  return result;
}

/** 教务连接状态文案。 */
export function eduStateText(state: string): string {
  const map: Record<string, string> = {
    'idle': '未连接', 'connecting': '连接中…', 'auth_required': '需要登录验证',
    'waiting_user_login': '等待用户登录', 'need_captcha': '需要完成人机验证',
    'need_slider': '需要完成滑块验证', 'need_sms': '需要短信验证码',
    'need_mfa': '需要多因素认证', 'authenticated': '已认证', 'syncing': '同步中…',
    'connected': '已连接', 'session_expired': '登录已过期，请重新登录',
    'auth_failed': '认证失败', 'network_error': '网络错误',
    'system_unavailable': '教务系统暂不可用', 'unsupported': '暂未完成适配',
    'error': '连接出错', 'active': '已连接', 'unbound': '未绑定',
  };
  return map[state] || state;
}

/** 教务连接状态文案（带 error_code，用于 waiting_user_login + NEED_CAPTCHA 等场景）。 */
export function eduStateTextWithErrorCode(state: string, errorCode?: string): string {
  if (state === 'waiting_user_login' && errorCode && errorCode.length > 0) {
    const codeMap: Record<string, string> = {
      'NEED_CAPTCHA': '学校要求完成图片验证码',
      'NEED_SLIDER': '需要完成滑块验证',
      'NEED_SMS': '需要短信验证码',
      'NEED_MFA': '需要多因素认证',
      'CLIENT_WEBVIEW': '请在学校登录页面完成验证',
      'NEED_CAMPUS_NETWORK': '请连接校园网或 VPN 后继续',
    };
    return codeMap[errorCode] || eduStateText(state);
  }
  return eduStateText(state);
}
