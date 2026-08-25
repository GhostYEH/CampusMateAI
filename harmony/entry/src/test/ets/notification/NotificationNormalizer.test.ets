import { describe, expect, it } from '@ohos/hypium';
import { CapturedNotification, NotificationNormalizer } from '../../../main/ets/data/notification/CapturedNotification';

export default function notificationNormalizerTest(): void {
  describe('NotificationNormalizer', () => {
    it('passes an IM notification title forward as a trusted whitelist candidate', 0, () => {
      const captured: CapturedNotification | null = NotificationNormalizer.normalize(
        'com.tencent.mm', 7, '软件工程一班（2条新消息）', '周五前提交课程论文', '', [], '', 1, ''
      );

      expect(captured?.groupCandidate).assertEqual('软件工程一班（2条新消息）');
      expect(captured?.groupIdentityConfidence).assertEqual('HIGH');
    });
  });
}
