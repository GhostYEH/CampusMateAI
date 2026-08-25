import { describe, expect, it } from '@ohos/hypium';
import { http } from '@kit.NetworkKit';
import { ChaoxingAccountStatus, ChaoxingStatusMapper, ChaoxingStatusResponse } from '../../../main/ets/data/chaoxing/ChaoxingAccount';
import { ChaoxingApiClient, ChaoxingRepository } from '../../../main/ets/data/chaoxing/ChaoxingRepository';

class FakeChaoxingApiClient implements ChaoxingApiClient {
  paths: string[] = [];
  noRefreshPaths: string[] = [];
  bodies: object[] = [];

  async request<T>(method: http.RequestMethod, path: string, body?: object): Promise<T> {
    this.paths.push(path);
    if (body !== undefined) this.bodies.push(body);
    const response: ChaoxingStatusResponse = { status: 'online', courses: 2, pending_assignments: 1, notices: 3 };
    return response as T;
  }

  async requestVoid(method: http.RequestMethod, path: string, body?: object): Promise<void> {
    this.paths.push(path);
    if (body !== undefined) this.bodies.push(body);
  }

  async requestVoidWithoutAuthRefresh(method: http.RequestMethod, path: string, body: object | undefined, unauthorizedMessage: string): Promise<void> {
    this.noRefreshPaths.push(path);
    if (body !== undefined) this.bodies.push(body);
  }
}

export default function chaoxingAccountTest(): void {
  describe('ChaoxingStatusMapper', () => {
    it('maps an online backend response to a connected account summary', 0, () => {
      const status: ChaoxingAccountStatus = ChaoxingStatusMapper.fromResponse({
        status: 'online',
        last_synced_at: '2026-08-23T10:30:00',
        source: 'chaoxing_live',
        courses: 4,
        teachers: 3,
        pending_assignments: 2,
        notices: 8,
        warnings: []
      });

      expect(status.connected).assertTrue();
      expect(status.requiresLogin).assertFalse();
      expect(status.canSync).assertTrue();
      expect(status.summary).assertEqual('4 门课程 · 2 项待交 · 8 条通知');
    });

    it('maps expired and offline responses to login-required states', 0, () => {
      const expired: ChaoxingAccountStatus = ChaoxingStatusMapper.fromResponse({ status: 'expired' });
      const offline: ChaoxingAccountStatus = ChaoxingStatusMapper.fromResponse({ status: 'offline' });

      expect(expired.connected).assertFalse();
      expect(expired.requiresLogin).assertTrue();
      expect(expired.label).assertEqual('需重新登录');
      expect(offline.requiresLogin).assertTrue();
      expect(offline.label).assertEqual('未连接');
    });

    it('does not claim a connection when status checking is unavailable', 0, () => {
      const status: ChaoxingAccountStatus = ChaoxingStatusMapper.fromResponse({ status: 'unavailable' });

      expect(status.connected).assertFalse();
      expect(status.requiresLogin).assertFalse();
      expect(status.canSync).assertFalse();
      expect(status.label).assertEqual('暂不可用');
    });

    it('uses the same account endpoints and login payload as Android', 0, async () => {
      const api: FakeChaoxingApiClient = new FakeChaoxingApiClient();
      const repository: ChaoxingRepository = new ChaoxingRepository(api);

      const status: ChaoxingAccountStatus = await repository.getStatus();
      await repository.login('student-1', 'secret-1');
      await repository.sync();
      await repository.disconnect();

      expect(status.summary).assertEqual('2 门课程 · 1 项待交 · 3 条通知');
      expect(api.paths.join(',')).assertEqual('chaoxing/status,chaoxing/sync,chaoxing/disconnect');
      expect(api.noRefreshPaths.join(',')).assertEqual('chaoxing/login');
      const loginBody: Record<string, string> = api.bodies[0] as Record<string, string>;
      expect(loginBody.username).assertEqual('student-1');
      expect(loginBody.password).assertEqual('secret-1');
    });
  });
}
