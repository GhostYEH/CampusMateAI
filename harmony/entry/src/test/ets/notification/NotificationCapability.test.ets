import { describe, expect, it } from '@ohos/hypium';
import { NotificationCaptureCapability, NotificationCaptureStatus } from '../../../main/ets/data/notification/NotificationCaptureCapability';

export default function notificationCapabilityTest(): void {
  describe('NotificationCaptureCapability', () => {
    it('reports ordinary unsigned phone builds as unavailable', 0, () => {
      const capability: NotificationCaptureCapability = NotificationCaptureCapability.ordinaryPhoneBuild();
      expect(capability.status).assertEqual(NotificationCaptureStatus.UNAVAILABLE);
      expect(capability.canStart()).assertFalse();
    });

    it('reports a granted notification subscription as supported', 0, () => {
      const capability: NotificationCaptureCapability = NotificationCaptureCapability.fromUserGrant(true);
      expect(capability.status).assertEqual(NotificationCaptureStatus.SUPPORTED);
      expect(capability.canStart()).assertTrue();
    });

    it('keeps the listener gated until the user grants access', 0, () => {
      const capability: NotificationCaptureCapability = NotificationCaptureCapability.fromUserGrant(false);
      expect(capability.status).assertEqual(NotificationCaptureStatus.NEEDS_PERMISSION);
      expect(capability.canStart()).assertFalse();
    });
  });
}
