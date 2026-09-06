import { common } from '@kit.AbilityKit';
import { describe, expect, it } from '@ohos/hypium';
import { NotificationCaptureStatus } from '../../../main/ets/data/notification/NotificationCaptureCapability';
import { NotificationPermissionGateway, NotificationSubscriberManager } from '../../../main/ets/data/notification/NotificationSubscriber';

class FakeNotificationPermissionGateway implements NotificationPermissionGateway {
  openSettingsCalls: number = 0;
  granted: boolean = false;

  async openSettings(_context: common.UIAbilityContext): Promise<void> {
    this.openSettingsCalls += 1;
    this.granted = true;
  }

  async isUserGranted(): Promise<boolean> {
    return this.granted;
  }
}

export default function notificationSubscriberTest(): void {
  describe('NotificationSubscriberManager', () => {
    it('opens the system authorization page and rechecks the result', 0, async () => {
      const gateway: FakeNotificationPermissionGateway = new FakeNotificationPermissionGateway();
      const manager: NotificationSubscriberManager = new NotificationSubscriberManager(gateway);
      const capability = await manager.requestPermission({} as common.UIAbilityContext);

      expect(gateway.openSettingsCalls).assertEqual(1);
      expect(capability.status).assertEqual(NotificationCaptureStatus.SUPPORTED);
      expect(manager.isSubscribed()).assertTrue();
    });

    it('does not reopen the authorization page when access is already granted', 0, async () => {
      const gateway: FakeNotificationPermissionGateway = new FakeNotificationPermissionGateway();
      gateway.granted = true;
      const manager: NotificationSubscriberManager = new NotificationSubscriberManager(gateway);
      const capability = await manager.requestPermission();

      expect(gateway.openSettingsCalls).assertEqual(0);
      expect(capability.status).assertEqual(NotificationCaptureStatus.SUPPORTED);
    });
  });
}
