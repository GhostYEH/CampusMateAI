import { CapturedNotification } from './CapturedNotification';
import { NotificationTextSanitizer } from './NotificationTextSanitizer';

const DEDUP_WINDOW_MS: number = 10 * 60 * 1000;
const UNIT_SEPARATOR: string = '\u001F';

export class NotificationFingerprint {
  static create(notification: CapturedNotification): string {
    const primaryText: string = NotificationTextSanitizer.primaryText(notification.bigText, notification.text);
    const timeBucket: string = Math.floor(notification.postTime / DEDUP_WINDOW_MS).toString();
    const identity: string = [
      notification.bundleName,
      notification.title,
      primaryText,
      notification.conversationTitle,
      timeBucket,
    ].join(UNIT_SEPARATOR);
    return NotificationFingerprint.fnv1a(identity);
  }

  private static fnv1a(input: string): string {
    let h1: number = 0x811c9dc5;
    let h2: number = 0x01000193;
    const prime: number = 0x01000193;
    for (let i: number = 0; i < input.length; i++) {
      const code: number = input.charCodeAt(i);
      h1 = Math.imul(h1 ^ code, prime) >>> 0;
      h2 = Math.imul(h2 ^ (code + 0x9e), prime) >>> 0;
    }
    const hex1: string = h1.toString(16).padStart(8, '0');
    const hex2: string = h2.toString(16).padStart(8, '0');
    return hex1 + hex2 + hex1 + hex2;
  }
}
