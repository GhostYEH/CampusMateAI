import { describe, expect, it } from '@ohos/hypium';
import { NotificationSource, NotificationSourceAliasRegistry, NotificationSourceResolver } from '../../../main/ets/data/notification/NotificationSource';

export default function notificationSourceResolverTest(): void {
  describe('NotificationSourceResolver', () => {
    it('resolves only registered aliases and supports enterprise WeChat', 0, () => {
      const registry: NotificationSourceAliasRegistry = new NotificationSourceAliasRegistry();
      registry.registerVerifiedAlias(NotificationSource.WECOM, 'verified.wecom.bundle');
      expect(NotificationSourceResolver.resolve('verified.wecom.bundle', registry)).assertEqual(NotificationSource.WECOM);
      expect(NotificationSourceResolver.resolve('guessed.wecom.bundle', registry)).assertEqual(NotificationSource.OTHER);
    });

    it('recognizes verified QQ and TIM aliases independently from WeChat', 0, () => {
      const registry: NotificationSourceAliasRegistry = NotificationSourceAliasRegistry.defaults();
      expect(NotificationSourceResolver.resolve('com.tencent.mobileqq', registry)).assertEqual(NotificationSource.QQ);
      expect(NotificationSourceResolver.resolve('com.tencent.tim', registry)).assertEqual(NotificationSource.QQ);
      expect(NotificationSourceResolver.resolve('com.tencent.mm', registry)).assertEqual(NotificationSource.WECHAT);
    });

    it('recognizes the enterprise WeChat bundle used by the aligned Android source', 0, () => {
      expect(NotificationSourceResolver.resolve('com.tencent.wework')).assertEqual(NotificationSource.WECOM);
    });
  });
}
