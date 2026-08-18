import { http } from '@kit.NetworkKit';
import { util } from '@kit.ArkTS';
import { ApiResponseParser } from './ApiResponse';
import { RefreshCoordinator } from './AuthRefresh';
import { AuthTokens, AuthTokensModel } from './auth/TokenStore';

const ENABLE_API_LOG: boolean = false;

export interface SseEvent {
  event: string;
  data: string;
}

function apiLog(message: string): void {
  if (ENABLE_API_LOG) console.log(`[API] ${message}`);
}

export interface ApiClientAuth {
  refreshTokenProvider: () => string;
  onTokens: (tokens: AuthTokens) => Promise<void>;
  onSessionExpired: () => Promise<void>;
}

export enum ApiErrorCode {
  SESSION_EXPIRED = 'SESSION_EXPIRED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  CONFLICT = 'CONFLICT',
  VALIDATION = 'VALIDATION',
  RATE_LIMITED = 'RATE_LIMITED',
  SERVER = 'SERVER',
  NETWORK = 'NETWORK'
}

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly statusCode: number;
  constructor(code: ApiErrorCode, message: string, statusCode: number = 0) {
    super(message);
    this.code = code;
    this.statusCode = statusCode;
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly tokenProvider: () => string;
  private readonly auth: ApiClientAuth | null;
  private static readonly refreshCoordinator: RefreshCoordinator = new RefreshCoordinator();

  constructor(baseUrl: string, tokenProvider: () => string, auth: ApiClientAuth | null = null) {
    this.baseUrl = baseUrl;
    this.tokenProvider = tokenProvider;
    this.auth = auth;
  }

  normalizedUrl(path: string): string {
    return `${this.baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
  }

  private createHttpError(statusCode: number): ApiError {
    switch (statusCode) {
      case 401: return new ApiError(ApiErrorCode.SESSION_EXPIRED, '登录已过期，请重新登录', statusCode);
      case 403: return new ApiError(ApiErrorCode.FORBIDDEN, '没有访问权限', statusCode);
      case 404: return new ApiError(ApiErrorCode.NOT_FOUND, '请求的服务不存在', statusCode);
      case 409: return new ApiError(ApiErrorCode.CONFLICT, '当前状态冲突，请刷新后重试', statusCode);
      case 422: return new ApiError(ApiErrorCode.VALIDATION, '请求数据格式错误', statusCode);
      case 429: return new ApiError(ApiErrorCode.RATE_LIMITED, '请求过于频繁，请稍后再试', statusCode);
      case 500: return new ApiError(ApiErrorCode.SERVER, '服务器内部错误，请稍后再试', statusCode);
      case 502: return new ApiError(ApiErrorCode.SERVER, '网关错误，请稍后再试', statusCode);
      case 503: return new ApiError(ApiErrorCode.SERVER, '服务暂时不可用', statusCode);
      case 504: return new ApiError(ApiErrorCode.NETWORK, '请求超时，请检查网络', statusCode);
      default: return new ApiError(ApiErrorCode.NETWORK, `请求失败 (${statusCode})`, statusCode);
    }
  }

  private buildHeaders(stream: boolean = false): Record<string, string> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (stream) headers.Accept = 'text/event-stream';
    const token: string = this.tokenProvider();
    if (token && token.length > 0) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  async login(username: string, password: string): Promise<AuthTokens> {
    const client = http.createHttp();
    const url: string = this.normalizedUrl('auth/login');
    apiLog(`POST ${url}`);
    try {
      const response = await client.request(url, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({ username: username, password: password }),
        connectTimeout: 10000,
        readTimeout: 15000
      });
      if (response.responseCode !== 200) throw this.createHttpError(response.responseCode);
      const data: Record<string, string> = ApiResponseParser.parseRequired<Record<string, string>>(response.result.toString());
      const accessToken: string | undefined = data.access_token;
      const refreshToken: string | undefined = data.refresh_token;
      if (!accessToken || accessToken.length === 0) throw new Error('登录响应中缺少 access_token');
      if (!refreshToken || refreshToken.length === 0) throw new Error('登录响应中缺少 refresh_token');
      return new AuthTokensModel(accessToken, refreshToken);
    } catch (e) {
      if (e instanceof Error) throw e;
      throw new Error('网络连接失败，请检查网络后重试');
    } finally {
      client.destroy();
    }
  }

  // ===== QR 扫码登录 =====
  async qrScan(sessionId: string, scanToken: string): Promise<QrScanResult> {
    return this.request<QrScanResult>(http.RequestMethod.POST, 'auth/qr/scan', {
      session_id: sessionId, scan_token: scanToken,
    });
  }

  async qrConfirm(sessionId: string, scanToken: string, trustDevice: boolean): Promise<QrConfirmResult> {
    return this.request<QrConfirmResult>(http.RequestMethod.POST, 'auth/qr/confirm', {
      session_id: sessionId, scan_token: scanToken, trust_device: trustDevice,
    });
  }

  async qrCancel(sessionId: string, scanToken: string): Promise<void> {
    await this.requestVoid(http.RequestMethod.POST, 'auth/qr/cancel', {
      session_id: sessionId, scan_token: scanToken,
    });
  }

  async request<T>(method: http.RequestMethod, path: string, body?: object): Promise<T> {
    const result: T | undefined = await this.executeRequest<T>(method, path, body, true);
    if (result === undefined) {
      throw new Error('服务器返回空数据');
    }
    return result;
  }

  async requestOptional<T>(method: http.RequestMethod, path: string, body?: object): Promise<T | undefined> {
    return this.executeRequest<T>(method, path, body, true);
  }

  async requestVoid(method: http.RequestMethod, path: string, body?: object): Promise<void> {
    await this.executeRequest<object>(method, path, body, true);
  }

  private async executeRequest<T>(method: http.RequestMethod, path: string, body: object | undefined, allowRefresh: boolean): Promise<T | undefined> {
    const client = http.createHttp();
    const url: string = this.normalizedUrl(path);
    apiLog(`${http.RequestMethod[method]} ${url}`);
    try {
      const response = await client.request(url, {
        method: method,
        header: this.buildHeaders(),
        extraData: body ? JSON.stringify(body) : undefined,
        connectTimeout: 10000,
        readTimeout: 15000
      });
      if (response.responseCode === 401 && allowRefresh && this.auth !== null) {
        const refreshed: boolean = await ApiClient.refreshCoordinator.run(() => this.refreshAccessToken());
        if (refreshed) {
          return this.executeRequest<T>(method, path, body, false);
        }
        await this.auth.onSessionExpired();
        throw this.createHttpError(401);
      }
      if (response.responseCode < 200 || response.responseCode >= 300) throw this.createHttpError(response.responseCode);
      return ApiResponseParser.parseOptional<T>(response.result.toString());
    } catch (e) {
      if (e instanceof Error) throw e;
      throw new Error('网络连接失败，请检查网络后重试');
    } finally {
      client.destroy();
    }
  }

  async refreshAccessToken(): Promise<boolean> {
    const auth: ApiClientAuth | null = this.auth;
    if (auth === null) return false;
    const refreshToken: string = auth.refreshTokenProvider();
    if (refreshToken.length === 0) return false;
    const client = http.createHttp();
    try {
      const response = await client.request(this.normalizedUrl('auth/refresh'), {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({ refresh_token: refreshToken }),
        connectTimeout: 10000,
        readTimeout: 15000
      });
      if (response.responseCode < 200 || response.responseCode >= 300) return false;
      const data: Record<string, string> = ApiResponseParser.parseRequired<Record<string, string>>(response.result.toString());
      const accessToken: string = data.access_token ?? '';
      const nextRefreshToken: string = data.refresh_token ?? '';
      if (accessToken.length === 0 || nextRefreshToken.length === 0) return false;
      await auth.onTokens(new AuthTokensModel(accessToken, nextRefreshToken));
      return true;
    } catch (_) {
      return false;
    } finally {
      client.destroy();
    }
  }

  async requestBinary(path: string): Promise<ArrayBuffer> {
    const client = http.createHttp();
    const url: string = this.normalizedUrl(path);
    try {
      const response = await client.request(url, {
        method: http.RequestMethod.GET,
        header: this.buildHeaders(),
        connectTimeout: 10000,
        readTimeout: 60000
      });
      if (response.responseCode < 200 || response.responseCode >= 300) throw this.createHttpError(response.responseCode);
      if (response.result instanceof ArrayBuffer) return response.result;
      return new util.TextEncoder().encode(response.result.toString()).buffer;
    } finally {
      client.destroy();
    }
  }

  /**
   * Reads an SSE response incrementally. Network chunks are not guaranteed to
   * align with SSE lines, so the parser retains incomplete lines between events.
   */
  async streamSse(path: string, body: object, onEvent: (event: SseEvent) => void): Promise<void> {
    const client = http.createHttp();
    const url = this.normalizedUrl(path);
    let buffer = '';
    let currentEvent = '';
    let dataLines: string[] = [];
    let completed = false;
    const decoder = new util.TextDecoder();
    let resolveStream: (() => void) | undefined;
    let rejectStream: ((error: Error) => void) | undefined;

    const dispatch = (): void => {
      if (dataLines.length > 0) onEvent({ event: currentEvent || 'message', data: dataLines.join('\n') });
      currentEvent = '';
      dataLines = [];
    };
    const consumeLine = (raw: string): void => {
      const line = raw.endsWith('\r') ? raw.substring(0, raw.length - 1) : raw;
      if (line.length === 0) {
        dispatch();
      } else if (line.startsWith('event:')) {
        currentEvent = line.substring(6).replace(/^ /, '');
      } else if (line.startsWith('data:')) {
        dataLines.push(line.substring(5).replace(/^ /, ''));
      }
    };
    const finish = (): void => {
      if (completed) return;
      completed = true;
      if (buffer.length > 0) consumeLine(buffer);
      dispatch();
      resolveStream?.();
    };

    try {
      const completion = new Promise<void>((resolve, reject) => {
        resolveStream = resolve;
        rejectStream = reject;
      });
      client.on('dataReceive', (chunk: ArrayBuffer) => {
        buffer += decoder.decode(new Uint8Array(chunk));
        let newline: number = buffer.indexOf('\n');
        while (newline >= 0) {
          consumeLine(buffer.substring(0, newline));
          buffer = buffer.substring(newline + 1);
          newline = buffer.indexOf('\n');
        }
      });
      client.on('dataEnd', () => finish());
      apiLog(`SSE POST ${url}`);
      const statusCode = await client.requestInStream(url, {
        method: http.RequestMethod.POST,
        header: this.buildHeaders(true),
        extraData: JSON.stringify(body),
        connectTimeout: 10000,
        readTimeout: 0
      });
      if (statusCode < 200 || statusCode >= 300) {
        completed = true;
        throw this.createHttpError(statusCode);
      }
      await completion;
    } catch (e) {
      if (e instanceof Error) throw e;
      throw new Error('AI 流式连接失败，请检查网络后重试');
    } finally {
      client.destroy();
    }
  }

  async patch<T>(path: string, body: object): Promise<T> {
    return this.request<T>('PATCH' as http.RequestMethod, path, body);
  }

  // ===== CampusMate EduConnector =====
  async eduDetect(universityId: string): Promise<EduDetectResult> {
    return this.request<EduDetectResult>('GET' as http.RequestMethod, `edu/detect?university_id=${encodeURIComponent(universityId)}`);
  }
  async getEduConfig(universityId: string): Promise<EduSystemConfigDto> {
    return this.request<EduSystemConfigDto>('GET' as http.RequestMethod, `edu/config/${encodeURIComponent(universityId)}`);
  }
  async getEduBinding(): Promise<EduBindingDto | undefined> {
    return this.requestOptional<EduBindingDto>('GET' as http.RequestMethod, 'edu/binding');
  }
  async eduBind(username: string, password: string, systemType: string = 'undergrad'): Promise<EduBindingDto> {
    const body: EduBindRequest = { username, password, system_type: systemType };
    return this.request<EduBindingDto>('POST' as http.RequestMethod, 'edu/bind', body);
  }
  async eduUnbind(): Promise<void> {
    return this.requestVoid('DELETE' as http.RequestMethod, 'edu/binding');
  }
  async eduSync(syncType: string, semester?: string): Promise<EduSyncResult> {
    const query = semester ? `?semester=${encodeURIComponent(semester)}` : '';
    return this.request<EduSyncResult>('POST' as http.RequestMethod, `edu/sync/${syncType}${query}`);
  }
  async getEduSyncRecords(limit: number = 20): Promise<EduSyncRecord[]> {
    return this.request<EduSyncRecord[]>('GET' as http.RequestMethod, `edu/sync/records?limit=${limit}`);
  }

  // ===== EduConnection 状态机（client_webview 登录流程） =====
  async eduProbe(portalUrl: string): Promise<EduProbeResult> {
    const body: EduProbeRequest = { portal_url: portalUrl };
    return this.request<EduProbeResult>('POST' as http.RequestMethod, 'edu/discovery/probe', body as object);
  }
  async eduCreateConnectionFromUrl(portalUrl: string, universityId?: string): Promise<EduConnectionDto> {
    const body: EduConnectionFromUrlRequest = { portal_url: portalUrl, university_id: universityId };
    return this.request<EduConnectionDto>('POST' as http.RequestMethod, 'edu/connections/from-url', body as object);
  }
  async eduGetConnection(connectionId: string): Promise<EduConnectionDto> {
    return this.request<EduConnectionDto>('GET' as http.RequestMethod, `edu/connections/${encodeURIComponent(connectionId)}`);
  }
  async eduContinueConnection(connectionId: string, body: EduConnectionContinueRequest): Promise<EduConnectionDto> {
    return this.request<EduConnectionDto>('POST' as http.RequestMethod, `edu/connections/${encodeURIComponent(connectionId)}/continue`, body as object);
  }
  async eduScheduleItems(semester?: string): Promise<EduScheduleItemsResponse> {
    const query = semester ? `?semester=${encodeURIComponent(semester)}` : '';
    return this.request<EduScheduleItemsResponse>('GET' as http.RequestMethod, `edu/schedule/items${query}`);
  }
  async eduGradeItems(semester?: string): Promise<EduGradeItemsResponse> {
    const query = semester ? `?semester=${encodeURIComponent(semester)}` : '';
    return this.request<EduGradeItemsResponse>('GET' as http.RequestMethod, `edu/grade/items${query}`);
  }
}

// ===== EduConnector 数据模型 =====
export interface EduDetectResult {
  university_id: string;
  provider: string;
  system_type: string;
  detected: boolean;
  confidence: string;
  reason?: string;
}
export interface EduSystemConfigDto {
  id: string;
  university_id: string;
  provider: string;
  system_type: string;
  academic_system_url?: string;
  academic_system_url_status: string;
  sso_url?: string;
  cas_url?: string;
  webvpn_url?: string;
  login_method: string;
  captcha_type: string;
  requires_campus_network?: boolean;
  supported_features: string[];
  school_code?: string;
  data_source: string;
}
export interface EduBindRequest {
  username: string;
  password: string;
  system_type: string;
}
export interface EduBindingDto {
  id: string;
  user_id: string;
  university_id: string;
  provider: string;
  system_type: string;
  external_student_id?: string;
  external_student_name?: string;
  status: string;
  last_synced_at?: string;
  last_sync_status?: string;
  last_error?: string;
}
export interface EduProfile {
  external_student_id?: string;
  name?: string;
  gender?: string;
  college?: string;
  major?: string;
  grade?: string;
  class_name?: string;
  enrollment_year?: string;
  schooling_length?: string;
}
export interface EduScheduleItem {
  course_name?: string;
  course_code?: string;
  teacher?: string;
  location?: string;
  weekday?: number;
  start_section?: number;
  end_section?: number;
  start_time?: string;
  end_time?: string;
  weeks?: string;
  semester?: string;
}
export interface EduSchedule { semester?: string; items: EduScheduleItem[]; }
export interface EduGradeItem {
  course_name?: string;
  course_code?: string;
  credit?: number;
  score?: string;
  grade_point?: number;
  semester?: string;
  category?: string;
  status?: string;
}
export interface EduGrade { semester?: string; gpa?: number; items: EduGradeItem[]; }
export interface EduExamItem {
  course_name?: string;
  course_code?: string;
  exam_type?: string;
  location?: string;
  seat?: string;
  starts_at?: string;
  ends_at?: string;
  semester?: string;
  notes?: string;
}
export interface EduExam { semester?: string; items: EduExamItem[]; }
export interface EduSyncResult {
  sync_type: string;
  status: string;
  items_count: number;
  error_message?: string;
  profile?: EduProfile;
  schedule?: EduSchedule;
  grade?: EduGrade;
  exam?: EduExam;
}
export interface EduSyncRecord {
  id: string;
  binding_id: string;
  sync_type: string;
  status: string;
  items_count: number;
  error_message?: string;
  started_at: string;
  finished_at?: string;
}

// ===== EduConnection 状态机 =====
export interface EduConnectionDto {
  id: string;
  user_id?: string;
  edu_system_id?: string;
  university_id?: string;
  state: string;
  provider: string;
  login_execution_mode: string;
  external_student_id?: string;
  external_student_name?: string;
  error_code?: string;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
}
export interface EduProbeResult {
  portal_url: string;
  provider: string;
  provider_confidence: number;
  reachable: boolean;
  http_status?: number;
  final_url?: string;
  title?: string;
  is_edu_page: boolean;
  suggested_login_mode: string;
  evidence: object[];
  error?: string;
}
export interface EduConnectionFromUrlRequest {
  portal_url: string;
  university_id?: string;
}
export interface EduProbeRequest {
  portal_url: string;
}
export interface EduConnectionContinueRequest {
  username?: string;
  password?: string;
  captcha?: string;
  sms_code?: string;
  mfa_code?: string;
  action?: string;
  cookies?: Record<string, string>;
  current_url?: string;
  user_agent?: string;
}
export interface EduScheduleItemDto {
  id?: string;
  semester?: string;
  course_code?: string;
  course_name?: string;
  teacher?: string;
  teachers?: string[];
  location?: string;
  campus?: string;
  building?: string;
  classroom?: string;
  weekday?: number;
  start_section?: number;
  end_section?: number;
  start_time?: string;
  end_time?: string;
  weeks?: string;
  week_text?: string;
  credit?: number;
  course_nature?: string;
  course_category?: string;
  course_type?: string;
  teaching_class?: string;
  class_name?: string;
  college?: string;
  department?: string;
  assessment_method?: string;
  exam_type?: string;
  total_hours?: number;
  theory_hours?: number;
  practice_hours?: number;
  language?: string;
  note?: string;
  semester_id?: string;
  extra_info?: Record<string, Object>;
  is_stale?: boolean;
  last_seen_at?: string;
}
export interface EduScheduleItemsResponse {
  semester?: string;
  items_count: number;
  items: EduScheduleItemDto[];
}
export interface EduGradeItemDto {
  id?: string;
  semester?: string;
  course_code?: string;
  course_name?: string;
  credit?: number;
  score?: string;
  grade_point?: number;
  category?: string;
  status?: string;
  is_stale?: boolean;
  last_seen_at?: string;
}
export interface EduGradeItemsResponse {
  semester?: string;
  items_count: number;
  items: EduGradeItemDto[];
}

// ===== QR 扫码登录 DTO =====
export interface QrScanResult {
  session_id: string;
  browser_name?: string;
  os_name?: string;
  device_label?: string;
  expires_at: string;
  status: string;
}
export interface QrConfirmResult {
  session_id: string;
  status: string;
  trust_device: boolean;
}
