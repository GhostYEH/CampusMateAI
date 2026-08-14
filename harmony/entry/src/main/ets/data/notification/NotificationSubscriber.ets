import { notificationExtensionSubscription } from '@kit.NotificationKit';
import { NotificationIngestService } from './NotificationIngestService';
import { CapturedNotification, NotificationNormalizer } from './CapturedNotification';
import { NotificationCaptureCapability } from './NotificationCaptureCapability';

const TAG: string = '[NotificationSubscriber]';

export class NotificationSubscriberManager {
  private ingestService: NotificationIngestService | null = null;
  private subscribed: boolean = false;

  init(ingestService: NotificationIngestService): void {
    this.ingestService = ingestService;
  }

  async start(): Promise<boolean> {
    const capability: NotificationCaptureCapability = NotificationCaptureCapability.ordinaryPhoneBuild();
    if (!capability.canStart()) {
      this.subscribed = false;
      return false;
    }
    if (this.ingestService === null) {
      return false;
    }
    try {
      const info: notificationExtensionSubscription.NotificationExtensionSubscriptionInfo[] = [
        { addr: '00:00:00:00:00:00', type: notificationExtensionSubscription.SubscribeType.BLUETOOTH },
      ];
      await notificationExtensionSubscription.subscribe(info);
      this.subscribed = true;
      console.info(`${TAG} subscription started`);
      return true;
    } catch (e) {
      console.warn(`${TAG} subscribe failed: ${(e as Error).message}`);
      this.subscribed = false;
      return false;
    }
  }

  async stop(): Promise<void> {
    if (!this.subscribed) {
      return;
    }
    try {
      await notificationExtensionSubscription.unsubscribe();
    } catch (e) {
      console.warn(`${TAG} unsubscribe failed: ${(e as Error).message}`);
    }
    this.subscribed = false;
  }

  isSubscribed(): boolean { return this.subscribed; }

  handleNotificationInfo(bundleName: string, title: string, text: string, deliveryTime: number): void {
    try {
      if (bundleName.length === 0) {
        return;
      }
      const captured: CapturedNotification | null = NotificationNormalizer.normalize(
        bundleName,
        0,
        title,
        text,
        '',
        [],
        '',
        deliveryTime,
        '',
      );
      if (captured === null) {
        return;
      }
      const service: NotificationIngestService | null = this.ingestService;
      if (service === null) {
        return;
      }
      service.captureAndIngest(captured).then((result) => {
        if (result.success) {
          console.info(`${TAG} captured: ${result.fingerprint.substring(0, 16)} from ${bundleName}`);
        }
      }).catch((e: Error) => {
        console.warn(`${TAG} capture failed: ${e.message}`);
      });
    } catch (e) {
      console.warn(`${TAG} handle error: ${(e as Error).message}`);
    }
  }
}

export const notificationSubscriberManager: NotificationSubscriberManager = new NotificationSubscriberManager();
