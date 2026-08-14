import { describe, expect, it } from '@ohos/hypium';
import { AppState } from '../../../main/ets/core/AppState';
import { AuthTokens, AuthTokensModel, TokenStorage } from '../../../main/ets/data/auth/TokenStore';

class MemoryTokenStorage implements TokenStorage {
  tokens: AuthTokens = new AuthTokensModel('', '');
  async load(): Promise<AuthTokens> { return this.tokens; }
  async save(tokens: AuthTokens): Promise<void> { this.tokens = tokens; }
  async clear(): Promise<void> { this.tokens = new AuthTokensModel('', ''); }
}

export default function appStateTest() {
  describe('AppState', () => {
    it('stores both tokens and clears them on sign-out', 0, async () => {
      const storage: MemoryTokenStorage = new MemoryTokenStorage();
      const state: AppState = new AppState(storage);
      await state.signIn(new AuthTokensModel('access-1', 'refresh-1'));
      expect(state.accessToken).assertEqual('access-1');
      expect(state.refreshToken).assertEqual('refresh-1');
      await state.signOut();
      expect(state.accessToken).assertEqual('');
      expect(state.refreshToken).assertEqual('');
    });
  });
}
