import { common } from '@kit.AbilityKit';
import { notificationExtensionSubscription } from '@kit.NotificationKit';
import { ApiClient } from '../ApiClient';
import { ApiConfig } from '../../core/ApiConfig';
import { NotificationCaptureCapability } from './NotificationCaptureCapability';
import { CapturedNotification, NotificationNormalizer } from './CapturedNotification';
import { IngestResult, NotificationIngestService } from './NotificationIngestService';

const TAG: string = '[NotificationSubscriber]';

export interface NotificationPermissionGateway {
  openSettings(context: common.UIAbilityContext | undefined): Promise<void>;
  isUserGranted(): Promise<boolean>;
}

class PlatformNotificationPermissionGateway implements NotificationPermissionGateway {
  async openSettings(context: common.UIAbilityContext | undefined): Promise<void> {
    if (context === undefined) {
      throw new Error('通知授权需要 UIAbilityContext');
    }
    await notificationExtensionSubscription.openSubscriptionSettings(context);
  }

  async isUserGranted(): Promise<boolean> {
    return notificationExtensionSubscription.isUserGranted();
  }
}

const platformPermissionGateway: NotificationPermissionGateway = new PlatformNotificationPermissionGateway();

export class NotificationSubscriberManager {
  private ingestService: NotificationIngestService | null = null;
  private subscribed: boolean = false;
  private readonly permissionGateway: NotificationPermissionGateway;

  constructor(permissionGateway: NotificationPermissionGateway = platformPermissionGateway) {
    this.permissionGateway = permissionGateway;
  }

  init(ingestService: NotificationIngestService): void {
    this.ingestService = ingestService;
  }

  async refreshPermission(): Promise<NotificationCaptureCapability> {
    try {
      const granted: boolean = await this.permissionGateway.isUserGranted();
      this.subscribed = granted;
      return NotificationCaptureCapability.fromUserGrant(granted);
    } catch (e) {
      this.subscribed = false;
      console.warn(`${TAG} permission status failed`);
      return NotificationCaptureCapability.ordinaryPhoneBuild();
    }
  }

  async requestPermission(context?: common.UIAbilityContext): Promise<NotificationCaptureCapability> {
    try {
      if (!(await this.permissionGateway.isUserGranted())) {
        await this.permissionGateway.openSettings(context);
      }
      return await this.refreshPermission();
    } catch (e) {
      this.subscribed = false;
      console.warn(`${TAG} permission request failed`);
      return NotificationCaptureCapability.error('无法打开系统通知授权页，请确认应用已获得通知订阅资质。');
    }
  }

  async start(): Promise<boolean> {
    const capability: NotificationCaptureCapability = await this.refreshPermission();
    return capability.canStart();
  }

  async stop(): Promise<void> {
    if (this.subscribed) {
      try {
        await notificationExtensionSubscription.unsubscribe();
      } catch (_) {
        console.warn(`${TAG} unsubscribe failed`);
      }
    }
    this.subscribed = false;
  }

  isSubscribed(): boolean { return this.subscribed; }

  handleNotificationInfo(bundleName: string, title: string, text: string, deliveryTime: number): void {
    if (bundleName.length === 0) return;
    try {
      const captured: CapturedNotification | null = NotificationNormalizer.normalize(
        bundleName, 0, title, text, '', [], '', deliveryTime, ''
      );
      if (captured === null) return;
      const service: NotificationIngestService = this.ingestService ?? this.createExtensionIngestService();
      this.ingestService = service;
      service.captureAndIngest(captured).then((result: IngestResult) => {
        if (result.success) console.info(`${TAG} captured ${result.fingerprint.substring(0, 16)}`);
      }).catch(() => {
        console.warn(`${TAG} capture failed`);
      });
    } catch (_) {
      console.warn(`${TAG} notification normalization failed`);
    }
  }

  private createExtensionIngestService(): NotificationIngestService {
    const apiClient: ApiClient = new ApiClient(ApiConfig.API_BASE_URL, () => '');
    // Extension callbacks run in their own ability process. They can still
    // persist the local inbox; authenticated backend sync remains UI-owned.
    return new NotificationIngestService(apiClient, () => '');
  }
}

export const notificationSubscriberManager: NotificationSubscriberManager = new NotificationSubscriberManager();
