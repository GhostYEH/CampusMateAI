import { http } from '@kit.NetworkKit';
import { ChaoxingAccountStatus, ChaoxingFailure, ChaoxingStatusMapper, ChaoxingStatusResponse } from './ChaoxingAccount';

export interface ChaoxingApiClient {
  request<T>(method: http.RequestMethod, path: string, body?: object): Promise<T>;
  requestVoid(method: http.RequestMethod, path: string, body?: object): Promise<void>;
  requestVoidWithoutAuthRefresh(method: http.RequestMethod, path: string, body: object | undefined, unauthorizedMessage: string): Promise<void>;
}

export interface ChaoxingLoginRequest {
  username: string;
  password: string;
}

export class ChaoxingRepository {
  private readonly apiClient: ChaoxingApiClient;
  private lastStatus: ChaoxingAccountStatus = ChaoxingStatusMapper.unavailable();

  constructor(apiClient: ChaoxingApiClient) {
    this.apiClient = apiClient;
  }

  async getStatus(): Promise<ChaoxingAccountStatus> {
    try {
      const response: ChaoxingStatusResponse = await this.apiClient.request<ChaoxingStatusResponse>(
        http.RequestMethod.GET,
        'chaoxing/status'
      );
      this.lastStatus = ChaoxingStatusMapper.fromResponse(response);
    } catch (error) {
      this.lastStatus = ChaoxingStatusMapper.fromFailure(error as ChaoxingFailure, this.lastStatus);
      this.lastStatus.warnings = [(error as Error).message];
    }
    return this.lastStatus;
  }

  async login(username: string, password: string): Promise<void> {
    const body: ChaoxingLoginRequest = { username: username, password: password };
    await this.apiClient.requestVoidWithoutAuthRefresh(
      http.RequestMethod.POST,
      'chaoxing/login',
      body,
      '学习通账号或密码错误'
    );
    // A successful login confirms the binding even if its follow-up status
    // request is temporarily unavailable.
    this.lastStatus.rawStatus = 'online';
    this.lastStatus.label = '已连接';
    this.lastStatus.connected = true;
    this.lastStatus.requiresLogin = false;
    this.lastStatus.canSync = true;
    this.lastStatus.warnings = [];
  }

  async sync(): Promise<void> {
    try {
      await this.apiClient.requestVoid(http.RequestMethod.POST, 'chaoxing/sync');
    } catch (error) {
      this.lastStatus = ChaoxingStatusMapper.fromFailure(error as ChaoxingFailure, this.lastStatus);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    await this.apiClient.requestVoid(http.RequestMethod.POST, 'chaoxing/disconnect');
    this.lastStatus = ChaoxingStatusMapper.fromResponse({ status: 'offline' });
  }
}
