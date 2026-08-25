import { describe, expect, it } from '@ohos/hypium';
import { LocalCapturedNotice } from '../../../main/ets/data/Models';
import { NotificationInbox, NotificationMutationQueue } from '../../../main/ets/data/notification/NotificationInbox';
import { NotificationSource } from '../../../main/ets/data/notification/NotificationSource';
import { NotificationSourceSettings } from '../../../main/ets/data/notification/NotificationSource';

function notice(id: string, sourceType: string): LocalCapturedNotice {
  return {
    id: id,
    title: `通知 ${id}`,
    content: `内容 ${id}`,
    source: `群聊 ${id}`,
    source_type: sourceType,
    time: '2026-08-22T09:49:00.000Z',
    fingerprint: `fingerprint-${id}`,
    captured_at: 1,
  };
}

export default function notificationInboxTest(): void {
  describe('NotificationInbox', () => {
    it('filters local records by the selected app source', 0, () => {
      const records: LocalCapturedNotice[] = [notice('1', '微信'), notice('2', '企业微信'), notice('3', 'QQ')];

      expect(NotificationInbox.filter(records, NotificationSource.WECOM).length).assertEqual(1);
      expect(NotificationInbox.filter(records, NotificationSource.WECOM)[0].id).assertEqual('2');
      expect(NotificationInbox.filter(records, null).length).assertEqual(3);
    });

    it('removes only the selected local record without mutating the input', 0, () => {
      const records: LocalCapturedNotice[] = [notice('1', '微信'), notice('2', 'QQ')];
      const updated: LocalCapturedNotice[] = NotificationInbox.remove(records, '1');

      expect(updated.length).assertEqual(1);
      expect(updated[0].id).assertEqual('2');
      expect(records.length).assertEqual(2);
    });

    it('trims whitelist names and rejects empty or duplicate groups', 0, () => {
      const initial: string[] = ['高数一班'];

      expect(NotificationInbox.addWhitelistGroup(initial, '  软件二班  ').length).assertEqual(2);
      expect(NotificationInbox.addWhitelistGroup(initial, ' 高数一班 ').length).assertEqual(1);
      expect(NotificationInbox.addWhitelistGroup(initial, '   ').length).assertEqual(1);
    });

    it('updates one source switch without changing the other source states', 0, () => {
      const settings: NotificationSourceSettings = {
        wechatEnabled: true,
        wecomEnabled: false,
        xuexitongEnabled: true,
        qqEnabled: false,
        otherEnabled: false,
      };

      const updated: NotificationSourceSettings = NotificationInbox.updateSourceSetting(settings, NotificationSource.QQ, true);
      expect(updated.qqEnabled).assertTrue();
      expect(updated.wechatEnabled).assertTrue();
      expect(updated.wecomEnabled).assertFalse();
      expect(updated.xuexitongEnabled).assertTrue();
    });

    it('serializes overlapping local record mutations', 0, async () => {
      const queue: NotificationMutationQueue = new NotificationMutationQueue();
      const events: string[] = [];
      const first: Promise<void> = queue.enqueue(async () => {
        events.push('first-start');
        await Promise.resolve();
        events.push('first-end');
      });
      const second: Promise<void> = queue.enqueue(async () => {
        events.push('second-start');
        events.push('second-end');
      });

      await Promise.all([first, second]);
      expect(events.join(',')).assertEqual('first-start,first-end,second-start,second-end');
    });
  });
}
