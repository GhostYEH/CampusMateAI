import { CapturedNotification } from './CapturedNotification';
import { NotificationSource, NotificationSourceSettings, isSourceEnabled } from './NotificationSource';
import { NotificationTextSanitizer } from './NotificationTextSanitizer';
import { NotificationContentClassifier, Classification, ClassificationKind } from './NotificationContentClassifier';

const CAMPUSMATE_BUNDLE: string = 'com.example.campusmate';

export class NotificationFilter {
  static shouldStore(
    notification: CapturedNotification,
    settings: NotificationSourceSettings,
    wechatWhitelist: string[] = [],
  ): boolean {
    if (notification.bundleName === CAMPUSMATE_BUNDLE) {
      return false;
    }
    if (!isSourceEnabled(settings, notification.source)) {
      return false;
    }
    if (notification.source === NotificationSource.WECHAT) {
      if (wechatWhitelist.length === 0) {
        return false;
      }
      const candidateGroup: string = notification.conversationTitle.length > 0 ? notification.conversationTitle : notification.title;
      if (candidateGroup.length === 0 || !wechatWhitelist.includes(candidateGroup)) {
        return false;
      }
    }
    const primaryText: string = NotificationTextSanitizer.primaryText(notification.bigText, notification.text);
    if (NotificationTextSanitizer.clean(primaryText).length === 0) {
      return false;
    }
    if (NotificationContentClassifier.isHardExcluded(primaryText)) {
      return false;
    }
    if (!NotificationContentClassifier.isLikelyNonTask(primaryText)) {
      return true;
    }
    const heading: string = [notification.conversationTitle, notification.title].filter((s: string) => s.length > 0).join('\n');
    return !NotificationContentClassifier.isLikelyNonTask(heading) && NotificationContentClassifier.hasActionSignal(primaryText);
  }

  static classifyReason(notification: CapturedNotification): string {
    const primaryText: string = NotificationTextSanitizer.primaryText(notification.bigText, notification.text);
    const result: Classification = NotificationContentClassifier.classify(primaryText);
    const prefix: string = result.kind === ClassificationKind.ACCEPT ? 'ACCEPT' : 'IGNORE';
    return `${prefix}: ${result.reason}`;
  }
}