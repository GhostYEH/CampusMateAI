import { describe, expect, it } from '@ohos/hypium';
import { CapturedNotification } from '../../../main/ets/data/notification/CapturedNotification';
import { NotificationFingerprint } from '../../../main/ets/data/notification/NotificationFingerprint';
import { NotificationSource } from '../../../main/ets/data/notification/NotificationSource';

function notice(id: number): CapturedNotification {
  return {
    notificationKey: `key-${id}`, bundleName: 'com.tencent.mm', notificationId: id, appName: '微信',
    title: '软件工程1班', text: '请提交实验报告', bigText: '', additionalText: '',
    groupCandidate: '软件工程1班', groupIdentityConfidence: 'HIGH', category: '',
    postTime: 1000, source: NotificationSource.WECHAT
  };
}

export default function notificationFingerprintTest(): void {
  describe('NotificationFingerprint', () => {
    it('deduplicates the same delivered notification', 0, () => {
      expect(NotificationFingerprint.create(notice(1))).assertEqual(NotificationFingerprint.create(notice(1)));
    });

    it('keeps distinct notification identities distinct', 0, () => {
      expect(NotificationFingerprint.create(notice(1)) === NotificationFingerprint.create(notice(2))).assertFalse();
    });
  });
}
