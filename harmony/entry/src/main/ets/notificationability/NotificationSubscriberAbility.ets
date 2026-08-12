import { NotificationSubscriberExtensionAbility, notificationExtensionSubscription } from '@kit.NotificationKit';
import { notificationSubscriberManager } from '../data/notification/NotificationSubscriber';

class CampusNotificationSubscriberAbility extends NotificationSubscriberExtensionAbility {
  onReceiveMessage(notificationInfo: notificationExtensionSubscription.NotificationInfo): void {
    try {
      const bundleName: string = notificationInfo.bundleName;
      const content = notificationInfo.content;
      let title: string = '';
      let text: string = '';
      if (content !== undefined && content !== null) {
        title = content.title;
        text = content.text;
      }
      const deliveryTime: number = notificationInfo.deliveryTime !== undefined ? notificationInfo.deliveryTime : Date.now();
      notificationSubscriberManager.handleNotificationInfo(bundleName, title, text, deliveryTime);
    } catch (e) {
      console.warn(`[CampusNotificationSubscriber] onReceiveMessage error: ${(e as Error).message}`);
    }
  }

  onCancelMessages(hashCodes: Array<string>): void {}

  onDestroy(): void {
    console.info('[CampusNotificationSubscriber] onDestroy');
  }
}

export default CampusNotificationSubscriberAbility;
