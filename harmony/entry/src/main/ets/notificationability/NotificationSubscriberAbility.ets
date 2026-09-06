import { NotificationSubscriberExtensionAbility, notificationExtensionSubscription } from '@kit.NotificationKit';
import { notificationSubscriberManager } from '../data/notification/NotificationSubscriber';

export default class NotificationSubscriberAbility extends NotificationSubscriberExtensionAbility {
  onReceiveMessage(notificationInfo: notificationExtensionSubscription.NotificationInfo): void {
    try {
      const content = notificationInfo.content;
      const title: string = content?.title ?? '';
      const text: string = content?.text ?? '';
      const deliveryTime: number = notificationInfo.deliveryTime ?? Date.now();
      notificationSubscriberManager.handleNotificationInfo(notificationInfo.bundleName, title, text, deliveryTime);
    } catch (_) {
      console.warn('[CampusNotificationSubscriber] onReceiveMessage failed');
    }
  }

  onCancelMessages(_hashCodes: Array<string>): void {}

  onDestroy(): void {
    console.info('[CampusNotificationSubscriber] destroyed');
  }
}
