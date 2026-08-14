import { NotificationSource, NotificationSourceResolver } from './NotificationSource';
import { NotificationTextSanitizer } from './NotificationTextSanitizer';

export interface CapturedNotification {
  notificationKey: string;
  bundleName: string;
  notificationId: number;
  appName: string;
  title: string;
  text: string;
  bigText: string;
  additionalText: string;
  groupCandidate: string;
  groupIdentityConfidence: 'HIGH' | 'LOW' | 'NONE';
  category: string;
  postTime: number;
  source: NotificationSource;
}

export class NotificationNormalizer {
  static normalize(
    bundleName: string,
    notificationId: number,
    contentTitle: string,
    contentText: string,
    contentLongText: string,
    contentLines: string[],
    additionalText: string,
    deliveryTime: number,
    category: string,
  ): CapturedNotification | null {
    const title: string = NotificationTextSanitizer.clean(contentTitle);
    const text: string = NotificationTextSanitizer.clean(contentText);
    const cleanedLong: string = NotificationTextSanitizer.clean(contentLongText);
    const bigText: string = cleanedLong.length > 0 ? cleanedLong : NotificationTextSanitizer.joinedLines(contentLines);
    const cleanAdditional: string = NotificationTextSanitizer.clean(additionalText);
    if (title.length === 0 && text.length === 0 && bigText.length === 0) {
      return null;
    }
    return {
      notificationKey: `${bundleName}:${notificationId}:${deliveryTime}`,
      bundleName: bundleName,
      notificationId: notificationId,
      appName: NotificationSourceResolver.displayName(bundleName),
      title: title,
      text: text,
      bigText: bigText,
      additionalText: cleanAdditional,
      groupCandidate: '',
      groupIdentityConfidence: 'NONE',
      category: category,
      postTime: deliveryTime,
      source: NotificationSourceResolver.resolve(bundleName),
    };
  }
}
