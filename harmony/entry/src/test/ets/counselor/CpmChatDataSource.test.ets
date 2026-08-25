import { describe, expect, it } from '@ohos/hypium';
import { CpmChatDataSource, CpmMessageStatus } from '../../../main/ets/features/counselor/CpmChatDataSource';

export default function cpmChatDataSourceTest(): void {
  describe('CpmChatDataSource', () => {
    it('updates the same observed message for every chunk', 0, () => {
      const source = new CpmChatDataSource();
      source.addUserAndAssistant('问题', 10);
      const assistantId = source.getData(1).id;

      source.appendChunk(assistantId, '第一段');
      source.appendChunk(assistantId, '第二段');

      expect(source.totalCount()).assertEqual(2);
      expect(source.getData(1).content).assertEqual('第一段第二段');
      expect(source.getData(1).status).assertEqual(CpmMessageStatus.GENERATING);
    });

    it('completes and retains partial text on failure', 0, () => {
      const source = new CpmChatDataSource();
      source.addUserAndAssistant('问题', 20);
      const assistantId = source.getData(1).id;
      source.appendChunk(assistantId, '部分回答');
      source.fail(assistantId, '网络异常');

      expect(source.getData(1).content).assertEqual('部分回答');
      expect(source.getData(1).status).assertEqual(CpmMessageStatus.ERROR);
      expect(source.getData(1).errorMessage).assertEqual('网络异常');
    });
  });
}
