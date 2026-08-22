import { describe, expect, it } from '@ohos/hypium';
import { CapturedNotification } from '../../../main/ets/data/notification/CapturedNotification';
import { NotificationFilter } from '../../../main/ets/data/notification/NotificationFilter';
import { NotificationSource, NotificationSourceSettings } from '../../../main/ets/data/notification/NotificationSource';

function captured(source: NotificationSource, group: string, text: string): CapturedNotification {
  return {
    notificationKey: 'key', bundleName: 'bundle', notificationId: 1, appName: 'app', title: group,
    text: text, bigText: '', additionalText: '', groupCandidate: group,
    groupIdentityConfidence: 'HIGH', category: '', postTime: 1, source: source
  };
}

export default function notificationFilterTest(): void {
  describe('NotificationFilter', () => {
    const settings: NotificationSourceSettings = {
      wechatEnabled: true, wecomEnabled: true, qqEnabled: true,
      xuexitongEnabled: true, otherEnabled: false
    };

    it('rejects a WeChat message outside the WeChat whitelist', 0, () => {
      const accepted: boolean = NotificationFilter.shouldStore(
        captured(NotificationSource.WECHAT, '私人聊天', '明天下午三点交实验报告'),
        settings, ['软件工程1班'], [], []
      );
      expect(accepted).assertFalse();
    });

    it('uses an independent enterprise WeChat whitelist', 0, () => {
      const accepted: boolean = NotificationFilter.shouldStore(
        captured(NotificationSource.WECOM, '学院工作群（3条新消息）', '明天下午三点交实验报告'),
        settings, [], ['学院工作群'], []
      );
      expect(accepted).assertTrue();
    });

    it('uses an independent QQ whitelist', 0, () => {
      const accepted: boolean = NotificationFilter.shouldStore(
        captured(NotificationSource.QQ, '课程群', '周五前提交课程论文'),
        settings, [], [], ['课程群']
      );
      expect(accepted).assertTrue();
    });
  });
}
