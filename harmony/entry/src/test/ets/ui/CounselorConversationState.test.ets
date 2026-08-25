import { describe, expect, it } from '@ohos/hypium';
import { CounselorConversationState } from '../../../main/ets/features/counselor/CounselorConversationState';

export default function counselorConversationStateTest(): void {
  describe('CounselorConversationState', () => {
    it('shows suggested questions only before the first message is sent', 0, () => {
      expect(CounselorConversationState.showSuggestions(0)).assertTrue();
      expect(CounselorConversationState.showSuggestions(1)).assertFalse();
      expect(CounselorConversationState.showSuggestions(4)).assertFalse();
    });
  });
}
