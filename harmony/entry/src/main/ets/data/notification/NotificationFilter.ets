import { CapturedNotification } from './CapturedNotification';
import { NotificationSource, NotificationSourceSettings, isSourceEnabled } from './NotificationSource';
import { NotificationTextSanitizer } from './NotificationTextSanitizer';
import { NotificationContentClassifier, Classification, ClassificationKind } from './NotificationContentClassifier';
import { GroupNameNormalizer } from './GroupNameNormalizer';

const CAMPUSMATE_BUNDLE: string = 'com.example.campusmate';

export class NotificationFilter {
  static shouldStore(
    notification: CapturedNotification,
    settings: NotificationSourceSettings,
    wechatWhitelist: string[] = [],
    wecomWhitelist: string[] = [],
    qqWhitelist: string[] = [],
  ): boolean {
    if (notification.bundleName === CAMPUSMATE_BUNDLE) {
      return false;
    }
    if (!isSourceEnabled(settings, notification.source)) {
      return false;
    }
    let sourceWhitelist: string[] | null = null;
    if (notification.source === NotificationSource.WECHAT) sourceWhitelist = wechatWhitelist;
    if (notification.source === NotificationSource.WECOM) sourceWhitelist = wecomWhitelist;
    if (notification.source === NotificationSource.QQ) sourceWhitelist = qqWhitelist;
    if (sourceWhitelist !== null) {
      if (sourceWhitelist.length === 0 || notification.groupIdentityConfidence !== 'HIGH') {
        return false;
      }
      if (!GroupNameNormalizer.matches(notification.groupCandidate, sourceWhitelist)) {
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
    const heading: string = [notification.groupCandidate, notification.title].filter((s: string) => s.length > 0).join('\n');
    return !NotificationContentClassifier.isLikelyNonTask(heading) && NotificationContentClassifier.hasActionSignal(primaryText);
  }

  static classifyReason(notification: CapturedNotification): string {
    const primaryText: string = NotificationTextSanitizer.primaryText(notification.bigText, notification.text);
    const result: Classification = NotificationContentClassifier.classify(primaryText);
    const prefix: string = result.kind === ClassificationKind.ACCEPT ? 'ACCEPT' : 'IGNORE';
    return `${prefix}: ${result.reason}`;
  }
}
