import { describe, expect, it } from '@ohos/hypium';
import { NotificationCaptureCapability, NotificationCaptureStatus } from '../../../main/ets/data/notification/NotificationCaptureCapability';

export default function notificationCapabilityTest(): void {
  describe('NotificationCaptureCapability', () => {
    it('reports ordinary unsigned phone builds as unavailable', 0, () => {
      const capability: NotificationCaptureCapability = NotificationCaptureCapability.ordinaryPhoneBuild();
      expect(capability.status).assertEqual(NotificationCaptureStatus.UNAVAILABLE);
      expect(capability.canStart()).assertFalse();
    });
  });
}
