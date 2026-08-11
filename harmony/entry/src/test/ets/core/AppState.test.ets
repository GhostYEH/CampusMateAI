import { describe, expect, it } from '@ohos/hypium';
import { AppState } from '../../../../main/ets/core/AppState';

export default function appStateTest() {
  describe('AppState', () => {
    it('stores a signed-in session and clears it on sign-out', 0, () => {
      const state = new AppState();
      state.signIn('token-1');
      expect(state.sessionToken).assertEqual('token-1');
      state.signOut();
      expect(state.sessionToken).assertEqual('');
    });
  });
}
