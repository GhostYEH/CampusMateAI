import { http } from '@kit.NetworkKit';
import { ChaoxingAccountStatus, ChaoxingStatusMapper, ChaoxingStatusResponse } from './ChaoxingAccount';

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

  constructor(apiClient: ChaoxingApiClient) {
    this.apiClient = apiClient;
  }

  async getStatus(): Promise<ChaoxingAccountStatus> {
    const response: ChaoxingStatusResponse = await this.apiClient.request<ChaoxingStatusResponse>(
      http.RequestMethod.GET,
      'chaoxing/status'
    );
    return ChaoxingStatusMapper.fromResponse(response);
  }

  async login(username: string, password: string): Promise<void> {
    const body: ChaoxingLoginRequest = { username: username, password: password };
    await this.apiClient.requestVoidWithoutAuthRefresh(
      http.RequestMethod.POST,
      'chaoxing/login',
      body,
      '学习通账号或密码错误'
    );
  }

  async sync(): Promise<void> {
    await this.apiClient.requestVoid(http.RequestMethod.POST, 'chaoxing/sync');
  }

  async disconnect(): Promise<void> {
    await this.apiClient.requestVoid(http.RequestMethod.POST, 'chaoxing/disconnect');
  }
}
