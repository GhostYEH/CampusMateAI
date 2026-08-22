import { describe, expect, it } from '@ohos/hypium';
import { ConversationBundle, ConversationBundler, QueuedNotification } from '../../../main/ets/data/notification/NotificationBatch';
import { NotificationSource } from '../../../main/ets/data/notification/NotificationSource';

function row(id: string, group: string, time: number): QueuedNotification {
  return { id: id, fingerprint: `fp-${id}`, source: NotificationSource.WECHAT,
    normalizedGroupName: group, text: `message-${id}`, publishedAt: time, retryCount: 0 };
}

export default function notificationBatchTest(): void {
  describe('ConversationBundler', () => {
    it('combines four nearby messages from the same normalized group', 0, () => {
      const bundles: ConversationBundle[] = ConversationBundler.bundle([
        row('1', '软件工程1班', 1000), row('2', '软件工程1班（2条新消息）', 2000),
        row('3', '软件工程1班', 3000), row('4', '软件工程1班', 4000)
      ]);
      expect(bundles.length).assertEqual(1);
      expect(bundles[0].messages.length).assertEqual(4);
    });

    it('never merges different groups', 0, () => {
      const bundles: ConversationBundle[] = ConversationBundler.bundle([
        row('1', '软件工程1班', 1000), row('2', '软件工程2班', 2000)
      ]);
      expect(bundles.length).assertEqual(2);
    });
  });
}
